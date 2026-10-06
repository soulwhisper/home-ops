#!/usr/bin/env python3
"""Compact a flate diff into a per-resource digest (R1 of homeops-rendering).

Reads the flate diff on stdin, prints a markdown digest on stdout:
one row per resource (kind ns/name, change class, +/- counts, image bumps
called out). Never breaks the pipeline: any parse surprise yields an empty
digest (caller keeps the raw diff in a details fold).
"""
import re
import sys

HEADER = re.compile(r"^\([^)]*\)\s{2,}\(([^)]+)\)\s*$")
ADDED = re.compile(r"document(s)? added", re.I)
REMOVED = re.compile(r"document(s)? removed", re.I)
IMAGE = re.compile(r"image:\s*(\S+)")


def split_key(key: str) -> tuple[str, str]:
    # group/version/Kind/namespace/name (namespace optional for cluster scope)
    parts = key.split("/")
    if len(parts) >= 5:
        return parts[2], "/".join(parts[3:])
    return parts[-1], key


def main() -> None:
    sections: list[dict] = []
    cur = None
    for raw in sys.stdin:
        line = raw.rstrip("\n")
        m = HEADER.match(line)
        if m:
            if cur:
                sections.append(cur)
            cur = {"key": m.group(1), "adds": 0, "dels": 0, "cls": "changed", "images": []}
            continue
        if cur is None:
            continue
        if ADDED.search(line):
            cur["cls"] = "added"
            continue
        if REMOVED.search(line):
            cur["cls"] = "removed"
            continue
        # real diff markers live at column 0; indented YAML list dashes and
        # added-doc content lines must not be miscounted
        if line.startswith("+"):
            cur["adds"] += 1
            im = IMAGE.search(line.lstrip("+"))
            if im:
                cur["images"].append(("in", im.group(1)))
        elif line.startswith("-"):
            cur["dels"] += 1
            im = IMAGE.search(line.lstrip("-"))
            if im:
                cur["images"].append(("out", im.group(1)))
        elif cur["cls"] == "added" and line.strip():
            cur["adds"] += 1
        elif cur["cls"] == "removed" and line.strip():
            cur["dels"] += 1
    if cur:
        sections.append(cur)

    if not sections:
        return

    rows = ["| Resource | Change | +/- |", "|---|---|---|"]
    images = []
    for s in sections:
        kind, name = split_key(s["key"])
        rows.append(f"| `{kind}` {name} | {s['cls']} | +{s['adds']}/-{s['dels']} |")
        images.extend((name, direction, img) for direction, img in s["images"])
    print("\n".join(rows))
    if images:
        print("\n**Image changes**")
        for name, direction, img in images:
            print(f"- `{name}` {'in' if direction == 'in' else 'out'}: {img}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # advisory: never break the pipeline
        print(f"<!-- compact_diff failed open: {exc} -->", file=sys.stderr)
