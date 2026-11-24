"""Compose preflight and healthcheck for the Synology downloader."""

from http.client import HTTPException
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from urllib.request import ProxyHandler, Request, build_opener, urlopen


def preflight():
    data = Path("/data")
    pics = data / "pics"
    for path in (data, pics, pics / "cards", pics / "tokens"):
        try:
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


def check_http(name, open_url, request, timeout):
    try:
        with open_url(request, timeout=timeout) as reply:
            if reply.status != 200:
                raise OSError(f"HTTP {reply.status}")
            reply.read()
    except (HTTPException, OSError) as exc:
        raise SystemExit(f"{name}: {exc}") from None


def health():
    local = build_opener(ProxyHandler({}))
    check_http("Downloader API", local.open, "http://127.0.0.1:8765/jobs", 3)
    request = Request("https://api.scryfall.com/sets/lea", headers={
        "Accept": "application/json", "User-Agent": "ForgeScryfallHealthcheck/1.0",
    })
    check_http("Scryfall API", urlopen, request, 5)


if __name__ == "__main__":
    {"preflight": preflight, "health": health}[sys.argv[1]]()
