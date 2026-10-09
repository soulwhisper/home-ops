#!/usr/bin/env python3
"""Distill one homelab-tickets issue into a learnings/ markdown file.

Single-shot LLM call (no tool loop): the ticket body + comments + the
lessons format guide go in, one markdown file comes out. Stdlib only.
"""
import datetime
import json
import os
import re
import sys
import urllib.request

FORGEJO_API = os.environ["FORGEJO_API"].rstrip("/")
REPO = os.environ["REPO"]
TOKEN = os.environ["FORGEJO_TOKEN"]
LLM_API_BASE = os.environ["LLM_API_BASE"].rstrip("/")
LLM_API_KEY = os.environ["LLM_API_KEY"]
LLM_MODEL = os.environ.get("LLM_MODEL", "agent")
TICKET = os.environ["TICKET"]


def get_json(url, headers):
    """GET url and decode the JSON response."""
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def post_json(url, headers, body):
    """POST body as JSON and decode the JSON response."""
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)


def get_all(url, headers, limit=50):
    """GET every page of a Forgejo list endpoint (server caps page size at 50)."""
    items, page = [], 1
    while True:
        batch = get_json(f"{url}?limit={limit}&page={page}", headers)
        items.extend(batch)
        if len(batch) < limit:
            return items
        page += 1


def slugify(title):
    """Lowercase, filesystem-safe slug of the ticket title (max 60 chars)."""
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:60] or "lesson"


forgejo = {"Authorization": f"token {TOKEN}", "Accept": "application/json"}
issue = get_json(f"{FORGEJO_API}/repos/{REPO}/issues/{TICKET}", forgejo)
# Every page: later comments carry the Holmes investigation, resolution and
# closing evidence the lesson must be distilled from.
comments = get_all(f"{FORGEJO_API}/repos/{REPO}/issues/{TICKET}/comments", forgejo)

with open("skills/lessons.md", encoding="utf-8") as f:
    fmt = f.read()

thread = "\n\n".join(
    f"--- comment by {c.get('user', {}).get('login', '?')} ---\n{c.get('body', '')}"
    for c in comments
)
user_prompt = (
    f"Ticket #{issue['number']}: {issue['title']}\n\n{issue.get('body') or ''}"
    f"\n\n{thread}\n\n"
    "Distill this into ONE lesson file per the format above. Output ONLY the "
    "markdown file content (frontmatter included), nothing else. If the ticket "
    "carries no reusable lesson, output exactly: NO_LESSON"
)

resp = post_json(
    f"{LLM_API_BASE}/chat/completions",
    {"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
    {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": "You write lessons per this format spec:\n\n" + fmt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    },
)
text = resp["choices"][0]["message"]["content"].strip()
if text == "NO_LESSON":
    print("ticket carries no reusable lesson; nothing written")
    sys.exit(0)

# strip a code fence if the model wrapped one
text = re.sub(r"^```(?:markdown)?\n|\n```$", "", text)

os.makedirs("learnings", exist_ok=True)
today = datetime.date.today().isoformat()
# ticket number keeps same-title tickets apart; the exists guard keeps a
# re-dispatch from overwriting manual edits to the first lesson
path = f"learnings/{today}-ticket{TICKET}-{slugify(issue['title'])}.md"
if os.path.exists(path):
    sys.exit(f"{path} already exists — refusing to overwrite; remove it first to re-distill")
with open(path, "x", encoding="utf-8") as f:
    f.write(text + "\n")
print(f"wrote {path}")
