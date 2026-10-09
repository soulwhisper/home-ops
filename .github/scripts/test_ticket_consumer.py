"""Exercise the ticket HTTP service against an isolated Forgejo API fixture."""
import copy
import importlib.util
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
import threading
import unittest
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "ticket_consumer", ROOT / "kubernetes/apps/monitoring-system/webhook-relay/app/ticket_consumer.py"
)
TICKETS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TICKETS)


class TicketLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.issues = []
        self.comments = {}
        self.fail_after_create = False
        owner = self

        class API(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                return

            def reply(self, status, payload):
                body = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                parts = urlsplit(self.path)
                items = (owner.comments.get(int(parts.path.split("/")[2]), [])
                         if parts.path.endswith("/comments") else owner.issues)
                query = parse_qs(parts.query)
                page, limit = int(query["page"][0]), int(query["limit"][0])
                self.reply(200, items[(page - 1) * limit:page * limit])

            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                if self.path.endswith("/comments"):
                    number = int(self.path.split("/")[2])
                    owner.comments.setdefault(number, []).append(payload)
                    self.reply(201, payload)
                else:
                    payload |= {"number": len(owner.issues) + 1, "state": "open"}
                    owner.issues.append(payload)
                    self.reply(503 if owner.fail_after_create else 201, payload)
                    owner.fail_after_create = False

            def do_PATCH(self):
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                number = int(self.path.split("/")[2])
                owner.issues[number - 1].update(payload)
                self.reply(200, owner.issues[number - 1])

        self.api = HTTPServer(("127.0.0.1", 0), API)
        backend = TICKETS.Forgejo(f"http://127.0.0.1:{self.api.server_port}", "fixture-token")
        handler = type("Consumer", (TICKETS.Handler,), {"forgejo": backend})
        self.consumer = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.threads = []
        for server in (self.api, self.consumer):
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.threads.append(thread)
        self.finding = {
            "source": "PROMETHEUS", "aggregation_key": "PodUnhealthy/default/example",
            "title": "Pod unhealthy", "severity": "HIGH", "failure": True,
            "fingerprint": "fixture", "id": "event-1", "creation_date": 1,
            "starts_at": "2026-10-09T00:00:00Z", "ends_at": None,
            "subject": {"kind": "Pod", "name": "example", "namespace": "default"},
            "description": "Readiness failure",
            "enrichments": [{"blocks": [{"text": "Diagnosis: startup failed"}]}],
        }

    def tearDown(self):
        for server in (self.consumer, self.api):
            server.shutdown()
            server.server_close()
        for thread in self.threads:
            thread.join()

    def deliver(self, finding=None):
        request = Request(
            f"http://127.0.0.1:{self.consumer.server_port}/findings",
            data=json.dumps(self.finding if finding is None else finding).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=5) as response:
            return json.load(response)

    def test_exact_replay_creates_one_issue_and_preserves_diagnosis(self):
        self.assertEqual(self.deliver()["action"], "created")
        self.assertEqual(self.deliver()["action"], "duplicate")
        self.assertEqual(len(self.issues), 1)
        self.assertEqual(self.comments, {})
        self.assertIn("Diagnosis: startup failed", self.issues[0]["body"])

    def test_concurrent_replays_create_only_one_incident(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _: self.deliver(), range(4)))
        self.assertEqual(len(self.issues), 1)
        self.assertEqual(self.comments, {})

    def test_changed_finding_and_resolution_share_timeline_without_auto_close(self):
        self.deliver()
        repeat = self.finding | {"id": "event-2", "creation_date": 2}
        self.deliver(repeat)
        resolution = repeat | {"id": "event-3", "failure": False, "ends_at": "2026-10-09T00:10:00Z"}
        self.deliver(resolution)
        self.deliver(resolution)
        self.assertEqual(len(self.issues), 1)
        self.assertEqual(len(self.comments[1]), 2)
        self.assertIn("**Event:** resolved", self.comments[1][-1]["body"])
        self.assertEqual(self.issues[0]["state"], "open")

    def test_exact_replay_does_not_undo_human_close_but_new_failure_reopens(self):
        self.deliver()
        self.issues[0]["state"] = "closed"
        self.deliver()
        self.assertEqual(self.issues[0]["state"], "closed")
        self.deliver(self.finding | {"id": "new-failure", "creation_date": 3})
        self.assertEqual(self.issues[0]["state"], "open")
        self.assertEqual(len(self.issues), 1)

    def test_resolution_without_incident_does_not_create_work(self):
        self.assertEqual(self.deliver(self.finding | {"failure": False})["action"], "unmatched-resolution")
        self.assertEqual(self.issues, [])

    def test_sources_do_not_collide_on_same_aggregation_key(self):
        self.deliver()
        self.deliver(self.finding | {"source": "KUBERNETES_API_SERVER"})
        self.assertEqual(len(self.issues), 2)

    def test_retry_after_ambiguous_create_success_does_not_duplicate(self):
        self.fail_after_create = True
        with self.assertRaises(HTTPError) as error:
            self.deliver()
        self.assertEqual(error.exception.code, 503)
        self.assertEqual(self.deliver()["action"], "duplicate")
        self.assertEqual(len(self.issues), 1)

    def test_issue_and_comment_pagination_preserves_dedupe(self):
        self.issues.extend({"number": n + 1, "body": "other incident", "state": "open"} for n in range(50))
        self.deliver()
        changed = self.finding | {"id": "later-event"}
        self.comments[51] = [{"body": "older comment"} for _ in range(50)]
        self.deliver(changed)
        self.deliver(changed)
        self.assertEqual(len(self.issues), 51)
        self.assertEqual(len(self.comments[51]), 51)

    def test_missing_identity_is_rejected_without_creating_issue(self):
        invalid = copy.deepcopy(self.finding)
        invalid.pop("aggregation_key")
        with self.assertRaises(HTTPError) as error:
            self.deliver(invalid)
        self.assertEqual(error.exception.code, 400)
        self.assertEqual(self.issues, [])


if __name__ == "__main__":
    unittest.main()
