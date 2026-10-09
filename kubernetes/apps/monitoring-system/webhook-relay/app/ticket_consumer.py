#!/usr/bin/env python3
"""Serialize Robusta findings into one Forgejo issue per alert instance."""
import hashlib
import json
import logging
import os
import queue
import re
import signal
import sys
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

MAX_PAYLOAD = 1024 * 1024
MAX_BODY = 60000
HOLMES_MARKER = "<!-- aiops-holmes -->"
HOLMES_COOLDOWN = timedelta(hours=6)
# Deployment pods are <workload>-<replicaset hash>-<pod hash>; StatefulSet
# pods (<name>-<ordinal>) are stable and keep their name.
POD_HASH = re.compile(r"-[a-z0-9]{6,10}-[a-z0-9]{5}$")
# Labels that identify *where* the condition is, as opposed to scrape plumbing
# (instance/pod IP/endpoint) or per-rule detail that would split one incident
# into dozens of tickets (e.g. one AlertingRulesError per rule group).
IDENTITY_LABELS = (
    "namespace", "exported_namespace", "workload", "deployment", "statefulset",
    "daemonset", "job_name", "cronjob", "pod", "container", "node",
    "persistentvolumeclaim", "name", "service",
)
LOG = logging.getLogger("tickets")


def incident_scope(finding):
    """Stable scope for one incident: alert-level labels, pods folded to workload."""
    labels = (finding.get("subject") or {}).get("labels") or {}
    scope = {}
    for key in IDENTITY_LABELS:
        value = labels.get(key)
        if isinstance(value, str) and value:
            scope[key] = POD_HASH.sub("", value) if key == "pod" else value
    return scope


class Forgejo:
    def __init__(self, repo_url, token):
        self.repo_url = repo_url.rstrip("/")
        self.token = token

    def request(self, method, path, data=None):
        body = json.dumps(data).encode() if data is not None else None
        request = Request(
            self.repo_url + path,
            data=body,
            headers={
                "Authorization": "token " + self.token,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method=method,
        )
        with urlopen(request, timeout=20) as response:
            content = response.read()
        return json.loads(content) if content else None

    def pages(self, path):
        separator = "&" if "?" in path else "?"
        page = 1
        while True:
            items = self.request("GET", f"{path}{separator}limit=50&page={page}")
            yield from items
            if len(items) < 50:
                return
            page += 1

    def find_issue(self, marker_hash):
        """Locate the incident issue; the search index is a hint, never the authority."""
        hint = self.request(
            "GET", f"/issues?state=all&type=issues&limit=50&q={quote('aiops-incident:' + marker_hash)}"
        )
        prefix = f"<!-- aiops-incident:{marker_hash} -->\n"
        match = next((i for i in hint or [] if (i.get("body") or "").startswith(prefix)), None)
        if match is not None:
            return match
        # Indexer lag or a cold index must not create a duplicate incident.
        return next(
            (item for item in self.pages("/issues?state=all&type=issues")
             if (item.get("body") or "").startswith(prefix)),
            None,
        )

    def deliver(self, finding):
        source = finding.get("source")
        key = finding.get("aggregation_key")
        if not isinstance(source, str) or not source or not isinstance(key, str) or not key:
            raise ValueError("source and aggregation_key are required")
        # One incident per alert + affected workload. Alertmanager fingerprints
        # change with every pod name and every per-rule label, so a rollout or
        # a rule-evaluation storm would otherwise open a ticket per pod/group.
        identity = json.dumps([source, key, incident_scope(finding)], separators=(",", ":"), sort_keys=True)
        marker_hash = hashlib.sha256(identity.encode()).hexdigest()
        marker = f"<!-- aiops-incident:{marker_hash} -->"
        resolved = finding.get("failure") is False or bool(finding.get("ends_at"))
        # One event per instance state transition. Robusta mints a fresh id,
        # creation_date and enrichments on every Alertmanager re-notification
        # (repeat_interval), so those must not count as a new observation.
        occurrence = json.dumps(
            [identity, finding.get("fingerprint"), resolved, finding.get("starts_at"), finding.get("ends_at")],
            separators=(",", ":"),
        )
        event_marker = f"<!-- aiops-event:{hashlib.sha256(occurrence.encode()).hexdigest()} -->"
        title = f"[{finding.get('severity', 'INFO')}] {finding.get('title', 'Robusta finding')}"[:250]
        body = format_finding(finding, resolved)[:MAX_BODY] + f"\n\n{event_marker}"
        issue = self.find_issue(marker_hash)
        if issue is None:
            if resolved:
                return {"action": "unmatched-resolution"}
            issue = self.request("POST", "/issues", {"title": title, "body": marker + "\n" + body})
            return {"action": "created", "number": issue["number"]}
        number = issue["number"]
        comments = list(self.pages(f"/issues/{number}/comments"))
        duplicate = event_marker in (issue.get("body") or "") or any(
            event_marker in (comment.get("body") or "") for comment in comments
        )
        if duplicate:
            return {"action": "duplicate", "number": number}
        # A new failure reopens the incident before recording its event. Exact
        # replays must not undo a later human close. Resolution never auto-closes.
        action = "commented"
        if not resolved and issue["state"] == "closed":
            self.request("PATCH", f"/issues/{number}", {"state": "open"})
            action = "reopened"
        self.request("POST", f"/issues/{number}/comments", {"body": body})
        return {"action": action, "number": number, "investigated_at": last_investigation(comments)}


def last_investigation(comments):
    stamps = [c.get("created_at") for c in comments if HOLMES_MARKER in (c.get("body") or "")]
    return max((s for s in stamps if s), default=None)


def investigation_due(result, now=None):
    """Investigate new incidents, and reopened ones not investigated recently."""
    if result["action"] == "created":
        return True
    if result["action"] != "reopened":
        return False
    stamp = result.get("investigated_at")
    if not stamp:
        return True
    last = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return (now or datetime.now(timezone.utc)) - last >= HOLMES_COOLDOWN


class Investigator:
    """Ask Holmes about new/reopened incidents and post the answer as a comment.

    Runs off the delivery lock: an LLM investigation takes minutes and must not
    stall chaski deliveries. The queue is in memory; a restart drops pending
    investigations, never tickets.
    """

    def __init__(self, holmes_url, forgejo, timeout=600):
        self.chat_url = holmes_url.rstrip("/") + "/api/chat"
        self.forgejo = forgejo
        self.timeout = timeout
        self.queue = queue.Queue(maxsize=20)

    def submit(self, number, finding):
        try:
            self.queue.put_nowait((number, finding))
        except queue.Full:
            LOG.warning("investigation queue full; skipped issue=%s", number)

    def run(self):
        while True:
            number, finding = self.queue.get()
            try:
                analysis = self.ask(number, finding)
                body = ("**Holmes investigation** (automated, unverified — "
                        "check the evidence before acting)\n\n"
                        + analysis[:MAX_BODY] + "\n\n" + HOLMES_MARKER)
                self.forgejo.request("POST", f"/issues/{number}/comments", {"body": body})
                LOG.info("investigation posted issue=%s", number)
            except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError, TypeError):
                LOG.error("Holmes investigation failed issue=%s", number)
            finally:
                self.queue.task_done()

    def ask(self, number, finding):
        request = Request(
            self.chat_url,
            data=json.dumps({"ask": investigation_prompt(number, finding)}).encode(),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout) as response:
            analysis = json.loads(response.read())["analysis"]
        if not isinstance(analysis, str) or not analysis.strip():
            raise ValueError("empty analysis")
        return analysis


def investigation_prompt(number, finding):
    subject = finding.get("subject") or {}
    labels = subject.get("labels") or {}
    return "\n".join([
        f"Investigate homelab incident ticket #{number}: {finding.get('title', '')}",
        f"Source: {finding.get('source')} | alert/key: {finding.get('aggregation_key')}",
        f"Subject: {subject.get('kind', '?')} {subject.get('name', '?')} "
        f"(namespace {subject.get('namespace') or '-'}, node {subject.get('node') or '-'})",
        f"Started: {finding.get('starts_at') or '-'}",
        f"Labels: {json.dumps(labels, sort_keys=True)[:2000]}",
        f"Description: {(finding.get('description') or '')[:4000]}",
        "",
        "Find the root cause with the metrics and logs tools. Reply in markdown with:",
        "## Root cause (state confidence: verified or suspected)",
        "## Evidence (each query you ran and what it showed)",
        "## Proposed fix (a GitOps change to the home-ops repo; never kubectl mutations)",
        "## Verification (the query or check that proves the fix worked)",
    ])


def format_finding(finding, resolved):
    subject = finding.get("subject") or {}
    lines = [
        "**Event:** " + ("resolved" if resolved else "finding"),
        f"**Source:** {finding['source']} | **Aggregation key:** `{finding['aggregation_key']}`",
        f"**Fingerprint:** `{finding.get('fingerprint') or '-'}`",
        f"**Subject:** {subject.get('kind', '?')} `{subject.get('name', '?')}` "
        f"(ns `{subject.get('namespace') or '-'}`)",
        f"**Started:** {finding.get('starts_at') or '-'} | **Ended:** {finding.get('ends_at') or '-'}",
        f"**Observed:** {finding.get('creation_date') or '-'}",
        "",
        finding.get("description") or "No description supplied.",
    ]
    for enrichment in finding.get("enrichments") or []:
        for block in enrichment.get("blocks") or []:
            if block.get("text"):
                lines.append(str(block["text"]))
            elif block.get("items"):
                lines.extend("- " + str(item) for item in block["items"])
            elif block.get("json_str"):
                lines.append(str(block["json_str"]))
    return "\n".join(lines)


class Handler(BaseHTTPRequestHandler):
    forgejo = None
    investigator = None
    delivery_lock = threading.Lock()

    def log_message(self, format, *args):
        # Never log request payloads, upstream response bodies, URLs or tokens.
        return

    def do_GET(self):
        self.respond(200 if self.path == "/healthz" else 404,
                     {"status": "ok"} if self.path == "/healthz" else {"error": "not found"})

    def do_POST(self):
        if self.path != "/findings":
            self.respond(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_PAYLOAD:
                self.respond(413, {"error": "invalid payload size"})
                return
            finding = json.loads(self.rfile.read(length))
            if not isinstance(finding, dict):
                raise ValueError("finding must be an object")
            with self.delivery_lock:
                result = self.forgejo.deliver(finding)
        except (ValueError, TypeError, KeyError):
            self.respond(400, {"error": "invalid finding"})
            return
        except (HTTPError, URLError, TimeoutError, OSError):
            LOG.error("Forgejo delivery failed")
            self.respond(503, {"error": "Forgejo delivery failed"})
            return
        LOG.info("delivery action=%s number=%s", result["action"], result.get("number", "-"))
        # Cooldown: a flapping incident reopens repeatedly; one investigation
        # per HOLMES_COOLDOWN is enough and keeps LLM load bounded.
        if self.investigator and investigation_due(result):
            self.investigator.submit(result["number"], finding)
        self.respond(200, {k: v for k, v in result.items() if k != "investigated_at"})

    def respond(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    logging.basicConfig(level=logging.INFO)
    signal.signal(signal.SIGTERM, lambda _signum, _frame: sys.exit(0))
    Handler.forgejo = Forgejo(os.environ["FORGEJO_REPO_URL"], os.environ["FORGEJO_TICKETS_TOKEN"])
    holmes_url = os.environ.get("HOLMES_URL")
    if holmes_url:
        Handler.investigator = Investigator(holmes_url, Handler.forgejo)
        threading.Thread(target=Handler.investigator.run, daemon=True).start()
    # No Service/remote listener: only chaski in this Pod can reach the consumer.
    # Serialize writes without blocking health probes on slow Forgejo requests.
    # 8081 belongs to chaski's metrics server.
    with ThreadingHTTPServer(("127.0.0.1", 8082), Handler) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
