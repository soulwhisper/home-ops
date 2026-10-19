#!/usr/bin/env python3
"""Unload ComfyUI models after five minutes without queued work."""
import json
import time
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:8188"
IDLE_SECONDS = 300
STATE = Path.home() / "ComfyUI" / "data" / "idle-offload.last-busy"


def request(path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        API + path,
        data=data,
        method="POST" if payload is not None else "GET",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        body = response.read()
    return json.loads(body) if body else {}


def main():
    now = time.time()
    queue = request("/queue")
    busy = bool(queue.get("queue_running") or queue.get("queue_pending"))
    if busy:
        STATE.write_text(str(now), encoding="utf-8")
        return

    try:
        idle_since = float(STATE.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        idle_since = now
        STATE.write_text(str(now), encoding="utf-8")
        return

    if now - idle_since >= IDLE_SECONDS:
        request("/free", {"unload_models": True, "free_memory": True})
        STATE.write_text(str(now), encoding="utf-8")
        print(f"unloaded ComfyUI models after {int(now - idle_since)}s idle", flush=True)


if __name__ == "__main__":
    main()
