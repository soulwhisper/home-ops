#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025-2026 soulwhisper (https://github.com/soulwhisper)
# SPDX-License-Identifier: Apache-2.0
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
RUN_ID = os.environ.get("RUN_ID", "")
ACTION_KEY = os.environ.get("ACTION_KEY", "")

if ACTION_KEY and not RUN_ID:
    sys.exit("RUN_ID is required when ACTION_KEY is set")
if RUN_ID and not ACTION_KEY:
    sys.exit("ACTION_KEY is required when RUN_ID is set")


def marker(name, value):
    """Reject unsafe machine identifiers without altering valid keys."""
    if re.search(r"[^a-zA-Z0-9_.:/@-]", value):
        sys.exit(f"{name} contains characters outside [a-zA-Z0-9_.:/@-]")
    return value


RUN_ID = marker("RUN_ID", RUN_ID)
ACTION_KEY = marker("ACTION_KEY", ACTION_KEY)
if RUN_ID and not re.fullmatch(r"[0-7][0-9A-HJKMNP-TV-Z]{25}", RUN_ID):
    sys.exit("RUN_ID must be a canonical 26-character Crockford Base32 ULID")
if ACTION_KEY and not re.fullmatch(
    rf"{re.escape(RUN_ID)}:lesson:[0-9a-f]{{40}}", ACTION_KEY
):
    sys.exit("ACTION_KEY must exactly match <RUN_ID>:lesson:<40 lowercase hex merge SHA>")


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


def workflow_timestamp(value):
    """Parse Forgejo timestamps, treating its zero time as absent."""
    if not value or value.startswith("0001-"):
        return None
    parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=datetime.timezone.utc)


def current_workflow_run():
    """Find the unique active supervised dispatch that is executing this script."""
    matches = []
    terminal = {"success", "failure", "cancelled", "skipped"}
    page = 1
    while True:
        payload = get_json(
            f"{FORGEJO_API}/repos/{REPO}/actions/runs?limit=50&page={page}", forgejo
        )
        runs = payload if isinstance(payload, list) else payload.get("workflow_runs", [])
        for run in runs:
            if run.get("workflow_id") != "lessons.yml" or run.get("status") in terminal:
                continue
            event = json.loads(run.get("event_payload") or "{}")
            if run.get("prettyref") != "main" and event.get("ref") != "refs/heads/main":
                continue
            inputs = event.get("inputs") or {}
            if (
                str(inputs.get("ticket")) == TICKET
                and str(inputs.get("run_id")) == RUN_ID
                and str(inputs.get("action_key")) == ACTION_KEY
            ):
                matches.append(run)
        if len(runs) < 50:
            break
        page += 1
    if len(matches) != 1:
        sys.exit(f"expected one active lessons workflow run, found {len(matches)}")
    return matches[0]


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

WORKFLOW_RUN = current_workflow_run() if ACTION_KEY else None

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
    status = ""
    if ACTION_KEY:
        no_lesson_marker = "<!-- aiops-no-lesson -->"
        action_marker = f"<!-- aiops-action:{ACTION_KEY} -->"
        run_line = f"aiops_run: {RUN_ID}"
        workflow_run_line = f"aiops_workflow_run: {WORKFLOW_RUN['id']}"
        required_lines = (no_lesson_marker, action_marker, run_line, workflow_run_line)
        trigger_id = (WORKFLOW_RUN.get("trigger_user") or {}).get("id")
        if trigger_id is None:
            sys.exit("workflow run has no trigger_user identity")
        started = workflow_timestamp(WORKFLOW_RUN.get("created"))
        stopped = workflow_timestamp(WORKFLOW_RUN.get("stopped"))
        already_present = False
        for comment in comments:
            body = comment.get("body") or ""
            lines = body.splitlines()
            if any(line not in lines for line in required_lines):
                continue
            if (comment.get("user") or {}).get("id") != trigger_id:
                continue
            created = workflow_timestamp(comment.get("created_at"))
            if started and (created is None or created < started):
                continue
            if stopped and (created is None or created > stopped):
                continue
            already_present = True
            break
        if not already_present:
            post_json(
                f"{FORGEJO_API}/repos/{REPO}/issues/{TICKET}/comments",
                {**forgejo, "Content-Type": "application/json"},
                {
                    "body": (
                        f"{no_lesson_marker}\n{action_marker}\n"
                        f"{run_line}\n{workflow_run_line}\n"
                        "No reusable lesson was found for this ticket; recorded for this run."
                    )
                },
            )
        status = (
            "keyed comment already present" if already_present else "keyed comment recorded"
        )
    suffix = f" | {status}" if status else ""
    print("ticket carries no reusable lesson; no lesson file written" + suffix)
    sys.exit(0)

# strip a code fence if the model wrapped one
text = re.sub(r"^```(?:markdown)?\n|\n```$", "", text)

if ACTION_KEY:
    if not text.startswith("---\n"):
        sys.exit("lesson missing YAML frontmatter; cannot embed aiops-action")
    text = f"---\naiops_action: {ACTION_KEY}\naiops_run: {RUN_ID}\n" + text[4:]

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
