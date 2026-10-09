#!/usr/bin/env python3
"""Serialize Robusta findings into one Forgejo issue per source/aggregation key."""
import hashlib
import json
import logging
import os
import signal
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MAX_PAYLOAD = 1024 * 1024
MAX_BODY = 16000
LOG = logging.getLogger("tickets")


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

    def deliver(self, finding):
        source = finding.get("source")
        key = finding.get("aggregation_key")
        if not isinstance(source, str) or not source or not isinstance(key, str) or not key:
            raise ValueError("source and aggregation_key are required")
        identity = json.dumps([source, key], separators=(",", ":"))
        marker = f"<!-- aiops-incident:{hashlib.sha256(identity.encode()).hexdigest()} -->"
        event = json.dumps(finding, sort_keys=True, separators=(",", ":"))
        event_marker = f"<!-- aiops-event:{hashlib.sha256(event.encode()).hexdigest()} -->"
        resolved = finding.get("failure") is False or bool(finding.get("ends_at"))
        title = f"[{finding.get('severity', 'INFO')}] {finding.get('title', 'Robusta finding')}"[:250]
        body = format_finding(finding, resolved)[:MAX_BODY] + f"\n\n{event_marker}"
        issue = next(
            (item for item in self.pages("/issues?state=all&type=issues")
             if (item.get("body") or "").startswith(marker + "\n")),
            None,
        )
        if issue is None:
            if resolved:
                return {"action": "unmatched-resolution"}
            issue = self.request("POST", "/issues", {"title": title, "body": marker + "\n" + body})
            return {"action": "created", "number": issue["number"]}
        number = issue["number"]
        duplicate = event_marker in (issue.get("body") or "") or any(
            event_marker in (comment.get("body") or "")
            for comment in self.pages(f"/issues/{number}/comments")
        )
        # A new failure reopens the incident before recording its event. Exact
        # replays must not undo a later human close. Resolution never auto-closes.
        if not duplicate:
            if not resolved and issue["state"] == "closed":
                self.request("PATCH", f"/issues/{number}", {"state": "open"})
            self.request("POST", f"/issues/{number}/comments", {"body": body})
        return {"action": "duplicate" if duplicate else "commented", "number": number}


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
        self.respond(200, result)

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
    # No Service/remote listener: only chaski in this Pod can reach the consumer.
    # Serialize writes without blocking health probes on slow Forgejo requests.
    # 8081 belongs to chaski's metrics server.
    with ThreadingHTTPServer(("127.0.0.1", 8082), Handler) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
