"""Deterministic stdlib collector regressions; never contact a cluster or model."""

import copy
import datetime
import importlib.util
import json
from pathlib import Path
import time
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[2] / "kubernetes/apps/monitoring-system/robusta/app/home_ops_collectors.py"
SPEC = importlib.util.spec_from_file_location("home_ops_collectors", SOURCE)
collectors = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collectors)
NOW = 1793250000.0


def timestamp(age):
    return datetime.datetime.fromtimestamp(NOW - age, datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def resource(name, status=None, namespace="database-system", spec=None, age=20 * 86400):
    return {"metadata": {"name": name, "namespace": namespace, "uid": name + "-uid",
                         "creationTimestamp": timestamp(age), "managedFields": [{"secret": "DO-NOT-OUTPUT"}]},
            "spec": spec or {}, "status": status or {}}


def sample(value, **labels):
    return {"metric": labels, "value": [NOW, str(value)]}


def backup(name, age, phase="completed"):
    return resource(name, {"phase": phase, "startedAt": timestamp(age), "stoppedAt": timestamp(age - 60)},
                    spec={"cluster": {"name": "postgres"}})


def job(name, age, success=True):
    obj = resource(name, {"succeeded": 1, "completionTime": timestamp(age - 120)} if success else {
        "failed": 1, "conditions": [{"type": "Failed", "status": "True"}]}, age=age)
    obj["metadata"]["ownerReferences"] = [{"kind": "CronJob", "name": "postgres-backup-verify",
                                             "uid": "postgres-backup-verify-uid"}]
    return obj


def snapshot(name, phase, start=None, end=None, created=60):
    timing = {}
    if start is not None:
        timing["startTime"] = timestamp(start)
    if end is not None:
        timing["endTime"] = timestamp(end)
    return resource(name, {"phase": phase, "timing": timing}, "apps", age=created)


def healthy_resources():
    return {
        collectors.CNPG: [backup("postgres-yesterday", 30 * 3600), backup("postgres-today", 6 * 3600)],
        collectors.CRON: [resource("postgres-backup-verify", {"lastSuccessfulTime": timestamp(60)},
                                    spec={"schedule": "0 4 * * 0"})],
        collectors.JOBS: [job("weekly-owned", 7 * 86400)],
        collectors.KOPIUR + "snapshotpolicies": [resource("app", namespace="apps")],
        collectors.KOPIUR + "clusterrepositories": [resource("nas", {
            "phase": "Ready", "conditions": [{"type": "Ready", "status": "True"},
                                                {"type": "BackendReachable", "status": "True"}]}, "")],
        collectors.KOPIUR + "snapshots": [snapshot("good", "Succeeded", 600, 500)]}


class FixtureReader(collectors.Reader):
    """Exercise production pagination, vector and rule parsing with fixture I/O."""

    def __init__(self, resources=None, page_size=2):
        self.resources = healthy_resources() if resources is None else resources
        self.page_size = page_size
        self.calls = []
        self.page_failures = {}
        self.page_versions = {}
        self.queries = {
            collectors.SUCCESS_METRIC: [sample(NOW - 600, namespace="apps", policy="app")],
            collectors.FAILURE_METRIC: [sample(0, namespace="apps", name="app")],
            collectors.CANDIDATES: []}
        self.rule_groups = []
        self.rules_payload = None

    def get(self, kube, path, params, deadline):
        collectors.remaining(deadline)
        params = dict(params)
        self.calls.append((kube, path, params))
        if kube:
            offset = int(params.get("continue", "0"))
            failure = self.page_failures.get((path, offset))
            if failure:
                raise failure
            rows = self.resources.get(path, [])
            end = min(offset + self.page_size, len(rows))
            return {"metadata": {"resourceVersion": self.page_versions.get((path, offset), "123"),
                                  "continue": str(end) if end < len(rows) else ""},
                    "items": copy.deepcopy(rows[offset:end])}
        if path == "/api/v1/query":
            value = self.queries.get(params["query"])
            if isinstance(value, Exception):
                raise value
            if isinstance(value, dict):
                return value
            if value is None:
                raise collectors.CollectionError("unexpected fixture expression")
            return {"status": "success", "data": {"resultType": "vector", "result": copy.deepcopy(value)}}
        if path == "/api/v1/rules":
            return self.rules_payload or {"status": "success", "data": {"groups": copy.deepcopy(self.rule_groups)}}
        raise AssertionError("unexpected boundary")


def run(reader, query=collectors.BACKUP):
    return collectors.collect_with_reader(query, time.monotonic() + 60, reader, now=NOW)


def categories(outcome):
    return {item["category"]: item for item in json.loads(outcome["rationale"])["categories"]}


class BackupTests(unittest.TestCase):
    def test_all_six_categories_have_coverage(self):
        outcome = run(FixtureReader())
        self.assertEqual(outcome["status"], "pass")
        self.assertEqual(len(categories(outcome)), 6)
        for category in categories(outcome).values():
            self.assertTrue(category["coverage_complete"])
            self.assertGreaterEqual(category["evaluated_count"], 1)
            self.assertLess(len(json.dumps(category)), 2000)
        self.assertNotIn("managedFields", outcome["rationale"])
        self.assertNotIn("DO-NOT-OUTPUT", outcome["rationale"])

    def test_cnpg_sorts_globally_across_pages_by_cluster_not_name(self):
        reader = FixtureReader(page_size=1)
        reader.resources[collectors.CNPG] = [backup("postgres-old", 100 * 86400),
                                           backup("manual-recent", 300), backup("postgres-middle", 86400)]
        other = backup("postgres-other-cluster", 10)
        other["spec"]["cluster"]["name"] = "another"
        reader.resources[collectors.CNPG].insert(1, other)
        category = categories(run(reader))["cnpg_daily_runs"]
        self.assertEqual(category["status"], "pass")
        self.assertEqual(category["evaluated_count"], 3)
        self.assertEqual([r["name"] for r in category["latest_runs"]], ["manual-recent", "postgres-middle"])

    def test_two_old_completed_runs_cannot_pass(self):
        reader = FixtureReader()
        reader.resources[collectors.CNPG] = [backup("old-a", 100 * 86400), backup("old-b", 101 * 86400)]
        self.assertEqual(categories(run(reader))["cnpg_daily_runs"]["status"], "fail")

    def test_cnpg_error_text_is_not_returned(self):
        reader = FixtureReader()
        reader.resources[collectors.CNPG][0]["status"]["error"] = "password=SUPERSECRET"
        outcome = run(reader)
        self.assertEqual(outcome["status"], "fail")
        self.assertNotIn("SUPERSECRET", outcome["rationale"])

    def test_missing_cnpg_start_is_error_not_missing_backup_proof(self):
        reader = FixtureReader()
        del reader.resources[collectors.CNPG][0]["status"]["startedAt"]
        category = categories(run(reader))["cnpg_daily_runs"]
        self.assertEqual(category["status"], "error")
        self.assertFalse(category["coverage_complete"])
        self.assertEqual(category["evaluated_count"], 2)

    def test_weekly_success_seven_days_old_passes(self):
        category = categories(run(FixtureReader()))["weekly_owned_jobs"]
        self.assertEqual(category["status"], "pass")

    def test_last_successful_time_is_not_execution_evidence(self):
        reader = FixtureReader()
        reader.resources[collectors.JOBS] = []
        self.assertEqual(categories(run(reader))["weekly_owned_jobs"]["status"], "fail")

    def test_foreign_owner_does_not_prove_success(self):
        reader = FixtureReader()
        reader.resources[collectors.JOBS][0]["metadata"]["ownerReferences"][0]["uid"] = "old-cronjob-uid"
        self.assertEqual(categories(run(reader))["weekly_owned_jobs"]["status"], "fail")

    def test_latest_owned_job_is_selected_across_pages(self):
        reader = FixtureReader(page_size=1)
        reader.resources[collectors.JOBS] = [job("old", 8 * 86400), job("new-failed", 60, False),
                                           job("middle", 4 * 86400)]
        category = categories(run(reader))["weekly_owned_jobs"]
        self.assertEqual(category["evaluated_count"], 3)
        self.assertEqual(category["latest_run"]["name"], "new-failed")
        self.assertEqual(category["status"], "fail")

    def test_historical_failed_job_does_not_override_latest_success(self):
        reader = FixtureReader(page_size=1)
        reader.resources[collectors.JOBS] = [job("old-failed", 8 * 86400, False), job("new-success", 86400)]
        category = categories(run(reader))["weekly_owned_jobs"]
        self.assertEqual(category["evaluated_count"], 2)
        self.assertEqual(category["status"], "pass")

    def test_new_weekly_target_not_yet_due(self):
        reader = FixtureReader()
        reader.resources[collectors.CRON][0]["metadata"]["creationTimestamp"] = timestamp(86400)
        reader.resources[collectors.JOBS] = []
        self.assertEqual(categories(run(reader))["weekly_owned_jobs"]["status"], "pass")

    def test_success_missing_completion_is_error(self):
        reader = FixtureReader()
        del reader.resources[collectors.JOBS][0]["status"]["completionTime"]
        self.assertEqual(categories(run(reader))["weekly_owned_jobs"]["status"], "error")

    def test_old_weekly_success_fails(self):
        reader = FixtureReader()
        reader.resources[collectors.JOBS] = [job("very-old", 11 * 86400)]
        self.assertEqual(categories(run(reader))["weekly_owned_jobs"]["status"], "fail")

    def test_every_policy_requires_both_metrics(self):
        reader = FixtureReader(page_size=1)
        reader.resources[collectors.KOPIUR + "snapshotpolicies"].append(resource("missing-metric", namespace="apps"))
        category = categories(run(reader))["kopiur_policies"]
        self.assertEqual(category["evaluated_count"], 2)
        self.assertEqual(category["status"], "error")
        self.assertFalse(category["coverage_complete"])

    def test_empty_or_unreachable_metric_never_passes(self):
        for value in ([], collectors.CollectionError("network or TLS request failed")):
            with self.subTest(value=value):
                reader = FixtureReader()
                reader.queries[collectors.SUCCESS_METRIC] = value
                self.assertEqual(categories(run(reader))["kopiur_policies"]["status"], "error")

    def test_stale_policy_or_consecutive_failures_is_finding(self):
        for success, failure in ((NOW - 90000, 0), (NOW - 60, 2)):
            with self.subTest(success=success, failure=failure):
                reader = FixtureReader()
                reader.queries[collectors.SUCCESS_METRIC] = [sample(success, namespace="apps", policy="app")]
                reader.queries[collectors.FAILURE_METRIC] = [sample(failure, namespace="apps", name="app")]
                self.assertEqual(categories(run(reader))["kopiur_policies"]["status"], "fail")

    def test_nas_backend_condition_is_required(self):
        reader = FixtureReader()
        reader.resources[collectors.KOPIUR + "clusterrepositories"][0]["status"]["conditions"].pop()
        self.assertEqual(categories(run(reader))["nas_repository"]["status"], "error")

    def test_false_repository_condition_is_finding(self):
        reader = FixtureReader()
        reader.resources[collectors.KOPIUR + "clusterrepositories"][0]["status"]["conditions"][1]["status"] = "False"
        self.assertEqual(categories(run(reader))["nas_repository"]["status"], "fail")

    def test_snapshots_evaluate_all_pages_and_count_all_findings(self):
        reader = FixtureReader(page_size=7)
        rows = [snapshot("stale-" + str(i), "Running", 3600 + i) for i in range(103)]
        rows += [snapshot("recent-failed-" + str(i), "Failed", 7200, 3600) for i in range(67)]
        rows += [snapshot("unstarted-" + str(i), "Pending", created=1000000) for i in range(29)]
        reader.resources[collectors.KOPIUR + "snapshots"] = rows
        category = categories(run(reader))["kopiur_snapshots"]
        self.assertEqual(category["evaluated_count"], 199)
        self.assertEqual(category["running_pending_over_30m"], 103)
        self.assertEqual(category["failed_recent"], 67)
        self.assertEqual(category["running_pending_missing_started"], 29)
        self.assertEqual(category["finding_count"], 170)
        self.assertTrue(category["coverage_complete"])
        self.assertLess(len(json.dumps(category)), 2000)
        self.assertLessEqual(len(category["representatives"]), 3)

    def test_missing_started_is_only_informational(self):
        reader = FixtureReader()
        reader.resources[collectors.KOPIUR + "snapshots"] = [snapshot("not-started", "Pending", created=1000000)]
        category = categories(run(reader))["kopiur_snapshots"]
        self.assertEqual(category["status"], "pass")
        self.assertEqual(category["running_pending_missing_started"], 1)
        self.assertEqual(category["running_pending_over_30m"], 0)

    def test_failed_uses_ended_then_created_only_when_ended_missing(self):
        reader = FixtureReader(page_size=1)
        reader.resources[collectors.KOPIUR + "snapshots"] = [
            snapshot("recent-ended-old-created", "Failed", end=60, created=900000),
            snapshot("old-ended-recent-created", "Failed", end=900000, created=60),
            snapshot("fallback-created", "Failed", created=60)]
        self.assertEqual(categories(run(reader))["kopiur_snapshots"]["failed_recent"], 2)

    def test_malformed_timing_does_not_skip_later_objects(self):
        reader = FixtureReader(page_size=1)
        malformed = snapshot("bad-time", "Running", 3600)
        malformed["status"]["timing"]["startTime"] = "bad"
        reader.resources[collectors.KOPIUR + "snapshots"] = [malformed, snapshot("stale", "Pending", 7200)]
        category = categories(run(reader))["kopiur_snapshots"]
        self.assertEqual(category["status"], "error")
        self.assertEqual(category["evaluated_count"], 2)
        self.assertEqual(category["running_pending_over_30m"], 1)

    def test_real_nonfailure_snapshot_phases_are_supported(self):
        reader = FixtureReader()
        reader.resources[collectors.KOPIUR + "snapshots"] = [snapshot(name, name) for name in
                                                               ("Succeeded", "Unchanged", "Discovered", "Deleting")]
        self.assertEqual(categories(run(reader))["kopiur_snapshots"]["status"], "pass")

    def test_midpage_failure_preserves_partial_count_but_not_coverage(self):
        reader = FixtureReader(page_size=1)
        reader.page_failures[(collectors.CNPG, 1)] = collectors.CollectionError("HTTP status 403")
        outcome = run(reader)
        category = categories(outcome)["cnpg_daily_runs"]
        self.assertEqual(outcome["status"], "error")
        self.assertEqual(category["evaluated_count"], 1)
        self.assertFalse(category["coverage_complete"])
        self.assertEqual(categories(outcome)["nas_repository"]["status"], "pass")

    def test_resource_version_change_is_not_a_consistent_scan(self):
        reader = FixtureReader(page_size=1)
        reader.page_versions[(collectors.CNPG, 1)] = "456"
        self.assertEqual(categories(run(reader))["cnpg_daily_runs"]["status"], "error")

    def test_snapshot_midpage_failure_retains_known_counts_and_findings(self):
        reader = FixtureReader(page_size=1)
        path = collectors.KOPIUR + "snapshots"
        reader.resources[path] = [snapshot("stale", "Running", 7200), snapshot("unread", "Failed", end=60)]
        reader.page_failures[(path, 1)] = collectors.CollectionError("HTTP status 403")
        category = categories(run(reader))["kopiur_snapshots"]
        self.assertEqual(category["status"], "error")
        self.assertEqual(category["evaluated_count"], 1)
        self.assertEqual(category["running_pending_over_30m"], 1)
        self.assertEqual(category["finding_count"], 1)


class ResolvedTests(unittest.TestCase):
    def fixture(self):
        reader = FixtureReader()
        reader.queries[collectors.CANDIDATES] = [sample(1, alertname="Alert", alertgroup="group")]
        reader.rule_groups = [{"name": "group", "file": "one.yaml", "id": "group-id", "type": "prometheus",
                               "rules": [{"name": "Alert", "id": "first", "type": "alerting", "query": "one > 1"},
                                         {"name": "Alert", "id": "second", "type": "alerting", "query": "two > 1"}]}]
        reader.queries["sum(absent(one > 1)) or vector(0)"] = [sample(1)]
        reader.queries["sum(absent(two > 1)) or vector(0)"] = [sample(1)]
        return reader

    def test_zero_candidates_proves_pass_without_rules_call(self):
        reader = FixtureReader()
        outcome = run(reader, collectors.RESOLVED)
        self.assertEqual(outcome["status"], "pass")
        self.assertEqual(categories(outcome)["resolved_alert_rules"]["candidate_count"], 0)
        self.assertFalse(any(call[1] == "/api/v1/rules" for call in reader.calls))

    def test_all_same_name_group_rules_are_evaluated(self):
        reader = self.fixture()
        reader.queries["sum(absent(two > 1)) or vector(0)"] = [sample(0)]
        # Preserve an additional matching group from another rule file.
        duplicate = copy.deepcopy(reader.rule_groups[0])
        duplicate.update(file="two.yaml", id="group-two")
        reader.rule_groups.append(duplicate)
        outcome = run(reader, collectors.RESOLVED)
        self.assertEqual(outcome["status"], "fail")
        evidence = json.loads(outcome["rationale"])["rule_evaluations"]
        self.assertEqual(categories(outcome)["resolved_alert_rules"]["evaluated_count"], 4)
        self.assertEqual(categories(outcome)["resolved_alert_rules"]["healed_count"], 2)
        self.assertEqual([row["numeric_result"] for row in evidence], [0, 0])
        self.assertEqual(len({row["stable_id"] for row in evidence}), 2)
        self.assertEqual([row["rule_index"] for row in evidence], [1, 1])
        self.assertNotIn("one > 1", outcome["rationale"])
        self.assertNotIn("two > 1", outcome["rationale"])

    def test_nonprometheus_rule_never_sent_to_query(self):
        reader = self.fixture()
        reader.rule_groups[0]["rules"][1].update(datasourceType="vlogs", query="DANGEROUS-LOGSQL")
        outcome = run(reader, collectors.RESOLVED)
        self.assertEqual(outcome["status"], "error")
        self.assertNotIn("DANGEROUS", outcome["rationale"])
        queries = [call[2].get("query", "") for call in reader.calls]
        self.assertFalse(any("DANGEROUS" in query for query in queries))
        self.assertEqual(json.loads(outcome["rationale"])["rule_evaluations"][0]["status"], "unevaluated")

    def test_error_or_invalid_absent_result_cannot_pass(self):
        for bad in ([], [sample(2)], [sample("NaN")], [sample(1), sample(0)],
                    collectors.CollectionError("query parse failed")):
            with self.subTest(bad=bad):
                reader = self.fixture()
                reader.queries["sum(absent(two > 1)) or vector(0)"] = bad
                self.assertEqual(run(reader, collectors.RESOLVED)["status"], "error")

    def test_rule_discovery_absence_or_truncation_cannot_pass(self):
        for payload in ({"status": "success", "data": {"groups": []}},
                        {"status": "success", "total_pages": 2, "data": {"groups": []}},
                        {"status": "success", "data": {"groups": [], "groupNextToken": "next"}},
                        {"status": "error", "error": "sensitive"}):
            with self.subTest(payload=payload):
                reader = self.fixture()
                reader.rules_payload = payload
                outcome = run(reader, collectors.RESOLVED)
                self.assertEqual(outcome["status"], "error")
                self.assertNotIn("sensitive", outcome["rationale"])

    def test_bounded_evidence_does_not_cap_rule_evaluation(self):
        reader = self.fixture()
        reader.rule_groups[0]["file"] = "long-file-" * 1000
        reader.rule_groups[0]["rules"] = []
        for index in range(42):
            expression = f"value_{index} > 0"
            reader.rule_groups[0]["rules"].append(
                {"name": "Alert", "id": str(index), "type": "alerting", "query": expression})
            reader.queries["sum(absent(" + expression + ")) or vector(0)"] = [sample(1 if index < 30 else 0)]
        outcome = run(reader, collectors.RESOLVED)
        self.assertEqual(outcome["status"], "fail")
        category = categories(outcome)["resolved_alert_rules"]
        self.assertTrue(category["coverage_complete"])
        self.assertEqual(category["evaluated_count"], 42)
        self.assertEqual(category["healed_count"], 30)
        self.assertEqual(category["finding_count"], 12)
        self.assertEqual(category["omitted_rule_evidence_count"], 4)
        evidence = json.loads(outcome["rationale"])["rule_evaluations"]
        self.assertEqual(len(evidence), 8)
        self.assertTrue(all(row["numeric_result"] == 0 for row in evidence))
        self.assertLess(len(outcome["rationale"]), 16000)

    def test_all_healed_is_pass(self):
        self.assertEqual(run(self.fixture(), collectors.RESOLVED)["status"], "pass")

    def test_candidate_query_error_does_not_become_zero_candidates(self):
        reader = self.fixture()
        reader.queries[collectors.CANDIDATES] = collectors.CollectionError("unreachable")
        self.assertEqual(run(reader, collectors.RESOLVED)["status"], "error")


class BoundaryTests(unittest.TestCase):
    def test_unknown_query_avoids_environment_and_io(self):
        with patch.object(collectors, "Reader", side_effect=AssertionError("must not construct")):
            self.assertIsNone(collectors.collect("other health check", time.monotonic() + 60))

    def test_expired_deadline_is_error(self):
        reader = FixtureReader()
        outcome = collectors.collect_with_reader(collectors.BACKUP, time.monotonic() - 1, reader, now=NOW)
        self.assertEqual(outcome["status"], "error")
        self.assertFalse(reader.calls)

    def test_production_reader_refuses_credential_urls_and_plaintext_remote_kubernetes(self):
        for endpoint in ("http://remote.cluster", "https://user:password@cluster", "https://cluster?token=secret"):
            with self.subTest(endpoint=endpoint), patch.dict(collectors.os.environ, {"HOME_OPS_KUBERNETES_URL": endpoint}):
                with self.assertRaises(collectors.CollectionError):
                    collectors.Reader()

    def test_partial_prometheus_response_is_error(self):
        reader = FixtureReader()
        reader.queries[collectors.CANDIDATES] = {"status": "success", "isPartial": True,
                                                 "data": {"resultType": "vector", "result": []}}
        self.assertEqual(run(reader, collectors.RESOLVED)["status"], "error")

    def test_http_redirects_are_refused(self):
        with self.assertRaises(collectors.CollectionError):
            collectors.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other")

    def test_oversized_page_is_narrowed_only_once(self):
        reader = FixtureReader()
        calls = []

        def oversized(kube, path, params, deadline):
            calls.append(dict(params))
            raise collectors.ResponseTooLarge("response exceeds bounded read size")

        reader.get = oversized
        with self.assertRaises(collectors.ResponseTooLarge):
            list(reader.kube_items(collectors.CNPG, time.monotonic() + 60))
        self.assertEqual([call["limit"] for call in calls], [50, 1])

    def test_repeated_continuation_is_error(self):
        reader = FixtureReader()
        reader.get = lambda *args: {"metadata": {"resourceVersion": "1", "continue": "same"}, "items": [{}]}
        with self.assertRaises(collectors.CollectionError):
            list(reader.kube_items(collectors.CNPG, time.monotonic() + 60))


if __name__ == "__main__":
    unittest.main()
