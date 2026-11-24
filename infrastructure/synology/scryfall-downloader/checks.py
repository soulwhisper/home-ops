"""Synology preflight, health, and first-start backfill."""

from contextlib import closing
from http.client import HTTPConnection, HTTPException
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from urllib.request import Request, urlopen


def preflight():
    data = Path("/state")
    pics = data / "pics"
    for path in (data, pics, pics / "cards", pics / "tokens"):
        try:
            if path.parent == pics:
                path.mkdir(exist_ok=True)
            if path.is_symlink() or not path.is_dir() or not os.access(path, os.R_OK | os.W_OK | os.X_OK):
                raise PermissionError("expected a readable, writable directory")
            with TemporaryDirectory(prefix=".scryfall-check-", dir=path) as scratch:
                probe = Path(scratch) / "probe"
                probe.write_bytes(b"ok")
                probe.chmod(0o644)
                if probe.replace(probe.with_name("published")).read_bytes() != b"ok":
                    raise OSError("could not read back the published file")
        except OSError as exc:
            raise SystemExit(f"{path} ({os.geteuid()}:{os.getegid()}): {exc}") from None


def health():
    probe = subprocess.run([sys.executable, "-m", "scryfall_downloader.healthcheck"], check=False)
    if probe.returncode:
        raise SystemExit("Downloader API: local worker probe failed")
    request = Request("https://api.scryfall.com/sets/lea", headers={
        "Accept": "application/json", "User-Agent": "ForgeScryfallHealthcheck/1.0",
    })
    try:
        with urlopen(request, timeout=5) as reply:
            if reply.status != 200:
                raise OSError(f"HTTP {reply.status}")
            reply.read()
    except (HTTPException, OSError) as exc:
        raise SystemExit(f"Scryfall API: {exc}") from None


def backfill():
    policy = json.loads(Path("/scryfall-backfill.json").read_text(encoding="utf-8"))
    blank = {**policy, "sets": [], "languages": ["zhs", "en"]}
    key = "home-ops:backfill:dmu-trk"
    with closing(HTTPConnection("scryfall-downloader", 8765, timeout=10)) as api:
        def request(method, suffix="", data=None, expected=200):
            path = "/api/v1/sync-list" + suffix
            headers = {}
            if data is not None:
                headers["Content-Type"] = "application/json"
            if method == "POST":
                headers["Idempotency-Key"] = key
            try:
                api.request(method, path, None if data is None else json.dumps(data), headers)
                with api.getresponse() as reply:
                    body = json.load(reply)
                    if reply.status != expected:
                        raise ValueError(f"HTTP {reply.status}: {body.get('error', 'unexpected response')}")
            except (OSError, HTTPException, ValueError) as exc:
                raise SystemExit(f"Backfill {method} {path}: {exc}") from None
            return body

        current = request("GET")
        saved = {field: current[field] for field in policy}
        log = {"entry_point": "compose_backfill", "request_id": key}
        if current["last_run_at"] is not None or saved not in (blank, policy):
            print(json.dumps({**log, "event": "backfill_skipped", "job_id": current["last_job_id"]}))
            return
        if saved == blank:
            request("PUT", data=policy)
        job = request("POST", "/run", {}, expected=202)
        print(json.dumps({**log, "event": "backfill_queued", "job_id": job["id"],
                          "sets": len(job["sets"]), "first_set": next(iter(job["sets"]))}))


if __name__ == "__main__":
    {"preflight": preflight, "health": health, "backfill": backfill}[sys.argv[1]]()
