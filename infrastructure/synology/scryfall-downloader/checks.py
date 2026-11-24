"""Compose preflight and healthcheck for the Synology downloader."""

from http.client import HTTPException
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


if __name__ == "__main__":
    {"preflight": preflight, "health": health}[sys.argv[1]]()
