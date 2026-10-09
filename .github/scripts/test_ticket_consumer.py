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
        self.index_lag = False  # simulate a search index that has not caught up
        self.searches = 0
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
                query = parse_qs(parts.query)
                if "q" in query:
                    owner.searches += 1
                    hits = [] if owner.index_lag else [
                        i for i in owner.issues if query["q"][0].split(":")[-1] in (i.get("body") or "")]
                    self.reply(200, hits)
                    return
                items = (owner.comments.get(int(parts.path.split("/")[2]), [])
                         if parts.path.endswith("/comments") else owner.issues)
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
            "subject": {"kind": "Pod", "name": "example", "namespace": "default",
                        "labels": {"alertname": "PodUnhealthy", "namespace": "default",
                                   "pod": "example-7d9f8b6c5d-x2k9q", "instance": "10.100.0.9:8080"}},
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
        refire = self.finding | {"id": "event-2", "starts_at": "2026-10-09T01:00:00Z"}
        self.deliver(refire)
        resolution = refire | {"id": "event-3", "failure": False, "ends_at": "2026-10-09T01:10:00Z"}
        self.deliver(resolution)
        self.deliver(resolution)
        self.assertEqual(len(self.issues), 1)
        self.assertEqual(len(self.comments[1]), 2)
        self.assertIn("**Event:** resolved", self.comments[1][-1]["body"])
        self.assertEqual(self.issues[0]["state"], "open")

    def test_renotification_of_same_state_is_suppressed(self):
        # Alertmanager repeat_interval re-sends a firing alert; Robusta mints a
        # new finding id, creation_date and fresh enrichments every time.
        self.deliver()
        renotify = self.finding | {
            "id": "event-9", "creation_date": 99,
            "enrichments": [{"blocks": [{"text": "Diagnosis: still failing"}]}],
        }
        self.assertEqual(self.deliver(renotify)["action"], "duplicate")
        self.assertEqual(self.comments, {})

    def labelled(self, **labels):
        finding = copy.deepcopy(self.finding)
        finding["subject"]["labels"] |= labels
        return finding

    def test_rollout_pods_of_one_workload_share_an_incident(self):
        self.deliver()
        new_pod = self.labelled(pod="example-5c6b7a8f9d-p3m4n", instance="10.100.1.7:8080")
        new_pod |= {"fingerprint": "new-pod", "starts_at": "2026-10-09T02:00:00Z"}
        self.assertEqual(self.deliver(new_pod)["action"], "commented")
        self.assertEqual(len(self.issues), 1)

    def test_different_workloads_get_separate_incidents(self):
        self.deliver()
        other = self.labelled(pod="other-7d9f8b6c5d-x2k9q") | {"fingerprint": "other"}
        self.assertEqual(self.deliver(other)["action"], "created")
        statefulset = self.labelled(pod="postgres-1") | {"fingerprint": "pg-1"}
        self.assertEqual(self.deliver(statefulset)["action"], "created")
        self.assertEqual(len(self.issues), 3)

    def test_per_rule_labels_do_not_split_one_alert(self):
        # AlertingRulesError carries one series per rule group/file.
        groups = [self.labelled(group=g, file=f"/rules/{g}.yaml", pod="vmalert-685d4c6c9-wwfmm")
                  | {"fingerprint": g, "starts_at": f"2026-10-09T00:0{n}:00Z"}
                  for n, g in enumerate(["etcd", "osd", "vmagent"])]
        for finding in groups:
            self.deliver(finding)
        self.assertEqual(len(self.issues), 1)
        self.assertEqual(len(self.comments[1]), 2)

    def test_concurrent_instances_resolve_independently(self):
        # Two pods of one workload fail at once; resolving one is not a replay of the other.
        self.deliver()
        second = self.labelled(pod="example-7d9f8b6c5d-zz9yy") | {"fingerprint": "second"}
        self.deliver(second)
        for fp, finding in (("fixture", self.finding), ("second", second)):
            self.deliver(finding | {"fingerprint": fp, "failure": False, "ends_at": "2026-10-09T03:00:00Z"})
        resolutions = [c for c in self.comments[1] if "**Event:** resolved" in c["body"]]
        self.assertEqual(len(resolutions), 2)

    def test_search_index_lag_falls_back_to_full_scan(self):
        self.deliver()
        self.index_lag = True
        refire = self.finding | {"starts_at": "2026-10-09T04:00:00Z"}
        self.assertEqual(self.deliver(refire)["action"], "commented")
        self.assertEqual(len(self.issues), 1)

    def test_indexed_lookup_avoids_scanning_unrelated_issues(self):
        self.issues.extend({"number": n + 1, "body": "other incident", "state": "open"} for n in range(120))
        self.deliver()
        scans = []
        original = TICKETS.Forgejo.pages
        TICKETS.Forgejo.pages = lambda inst, path: (scans.append(path), original(inst, path))[1]
        try:
            self.assertEqual(self.deliver()["action"], "duplicate")
        finally:
            TICKETS.Forgejo.pages = original
        self.assertFalse(any(p.startswith("/issues?") for p in scans))

    def test_exact_replay_does_not_undo_human_close_but_new_failure_reopens(self):
        self.deliver()
        self.issues[0]["state"] = "closed"
        self.deliver()
        self.assertEqual(self.issues[0]["state"], "closed")
        refire = self.finding | {"id": "new-failure", "starts_at": "2026-10-10T00:00:00Z"}
        self.assertEqual(self.deliver(refire)["action"], "reopened")
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
        self.index_lag = True
        self.issues.extend({"number": n + 1, "body": "other incident", "state": "open"} for n in range(50))
        self.deliver()
        changed = self.finding | {"id": "later-event", "starts_at": "2026-10-09T05:00:00Z"}
        self.comments[51] = [{"body": "older comment"} for _ in range(50)]
        self.deliver(changed)
        self.deliver(changed)
        self.assertEqual(len(self.issues), 51)
        self.assertEqual(len(self.comments[51]), 51)

    def test_missing_identity_is_rejected_without_creating_issue(self):
        for field in ("source", "aggregation_key"):
            invalid = copy.deepcopy(self.finding)
            invalid.pop(field)
            with self.assertRaises(HTTPError) as error:
                self.deliver(invalid)
            self.assertEqual(error.exception.code, 400)
        self.assertEqual(self.issues, [])


class InvestigationCooldownTest(unittest.TestCase):
    now = TICKETS.datetime(2026, 10, 9, 12, tzinfo=TICKETS.timezone.utc)

    def test_new_incident_is_investigated(self):
        self.assertTrue(TICKETS.investigation_due({"action": "created"}, self.now))

    def test_reopen_within_cooldown_is_skipped_and_after_is_investigated(self):
        recent = {"action": "reopened", "investigated_at": "2026-10-09T08:00:00Z"}
        stale = {"action": "reopened", "investigated_at": "2026-10-09T05:59:00Z"}
        self.assertFalse(TICKETS.investigation_due(recent, self.now))
        self.assertTrue(TICKETS.investigation_due(stale, self.now))
        self.assertTrue(TICKETS.investigation_due({"action": "reopened", "investigated_at": None}, self.now))

    def test_plain_comments_never_trigger_investigation(self):
        self.assertFalse(TICKETS.investigation_due({"action": "commented"}, self.now))


class HolmesInvestigationTest(unittest.TestCase):
    def setUp(self):
        self.asks = []
        self.comments = []
        self.reply = {"analysis": "## Root cause\nstartup probe too short"}
        owner = self

        class API(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                return

            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                if self.path == "/api/chat":
                    owner.asks.append(payload["ask"])
                    status, body = (200, owner.reply) if owner.reply else (500, {})
                else:
                    owner.comments.append((self.path, payload["body"]))
                    status, body = 201, payload
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.api = HTTPServer(("127.0.0.1", 0), API)
        threading.Thread(target=self.api.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{self.api.server_port}"
        self.investigator = TICKETS.Investigator(base, TICKETS.Forgejo(base, "fixture-token"), timeout=5)
        threading.Thread(target=self.investigator.run, daemon=True).start()
        self.finding = {"source": "PROMETHEUS", "aggregation_key": "PodUnhealthy", "title": "Pod unhealthy",
                        "subject": {"kind": "Pod", "name": "example", "namespace": "default"}}

    def tearDown(self):
        self.api.shutdown()
        self.api.server_close()

    def test_analysis_is_posted_to_the_ticket(self):
        self.investigator.submit(7, self.finding)
        self.investigator.queue.join()
        self.assertIn("#7", self.asks[0])
        self.assertEqual(self.comments[0][0], "/issues/7/comments")
        self.assertIn("startup probe too short", self.comments[0][1])
        self.assertIn(TICKETS.HOLMES_MARKER, self.comments[0][1])

    def test_holmes_failure_posts_nothing_and_keeps_worker_alive(self):
        self.reply = None
        self.investigator.submit(7, self.finding)
        self.investigator.queue.join()
        self.assertEqual(self.comments, [])
        self.reply = {"analysis": "recovered"}
        self.investigator.submit(8, self.finding)
        self.investigator.queue.join()
        self.assertEqual(self.comments[0][0], "/issues/8/comments")


if __name__ == "__main__":
    unittest.main()
