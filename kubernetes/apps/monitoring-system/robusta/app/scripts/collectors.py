"""Read-only fixed health checks; no Holmes dependency or model-generated queries.

The injectable reader implements kube_items(path, deadline, params=None) and
prom_query(expression, deadline), rules(name, group, deadline). The production
reader uses service-account TLS and GET only. CLI: python collectors.py
home-ops:backup-chain --timeout 300 (or home-ops:resolved-alert-recheck).
"""

import argparse
import datetime
import hashlib
import json
import math
import os
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

BACKUP = "home-ops:backup-chain"
RESOLVED = "home-ops:resolved-alert-recheck"
CANDIDATES = ('max by (alertname, alertgroup) (max_over_time(ALERTS{alertstate="firing"}[12h])) '
              'unless on(alertname, alertgroup) present_over_time(ALERTS{alertstate="firing"}[5m])')
CNPG = "/apis/postgresql.cnpg.io/v1/namespaces/database-system/backups"
CRON = "/apis/batch/v1/namespaces/database-system/cronjobs"
JOBS = "/apis/batch/v1/namespaces/database-system/jobs"
KOPIUR = "/apis/kopiur.home-operations.com/v1alpha1/"
SUCCESS_METRIC = "max by (namespace, policy) (kopiur_policy_last_backup_success_timestamp_seconds)"
FAILURE_METRIC = "max by (namespace, name) (kopiur_snapshot_consecutive_failures)"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024


class CollectionError(Exception):
    """Only fixed, non-sensitive messages may cross the reader boundary."""


class ResponseTooLarge(CollectionError):
    pass


def remaining(deadline):
    value = deadline - time.monotonic()
    if value <= 0:
        raise CollectionError("collection deadline exceeded")
    return value


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward service-account credentials or a rule expression elsewhere.
        raise CollectionError("HTTP redirect refused")


class Reader:
    """Bounded HTTP reads. Endpoint overrides never disable certificate checks."""

    def __init__(self):
        self.kube_url = os.environ.get("HOME_OPS_KUBERNETES_URL", "https://kubernetes.default.svc")
        self.prom_url = os.environ.get(
            "HOME_OPS_PROMETHEUS_URL",
            "http://vmsingle-victoria-metrics-cluster.monitoring-system.svc.cluster.local:8428")
        self.token_file = os.environ.get(
            "HOME_OPS_KUBERNETES_TOKEN_FILE", "/var/run/secrets/kubernetes.io/serviceaccount/token")
        self.ca_file = os.environ.get(
            "HOME_OPS_KUBERNETES_CA_FILE", "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt")
        self._kube_opener = None
        self._prom_opener = None
        for url in (self.kube_url, self.prom_url):
            parsed = urllib.parse.urlsplit(url)
            if parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise CollectionError("endpoint must not contain credentials, query or fragment")
            if parsed.scheme not in ("http", "https") or not parsed.hostname:
                raise CollectionError("invalid endpoint")
        if urllib.parse.urlsplit(self.kube_url).scheme != "https":
            # An explicit loopback proxy is useful for read-only local smoke.
            host = urllib.parse.urlsplit(self.kube_url).hostname
            if host not in ("localhost", "127.0.0.1", "::1"):
                raise CollectionError("Kubernetes endpoint requires HTTPS outside loopback")

    def _opener(self, kube):
        attr = "_kube_opener" if kube else "_prom_opener"
        opener = getattr(self, attr)
        if opener is None:
            try:
                context = ssl.create_default_context(cafile=self.ca_file if kube and self.kube_url.startswith("https:") else None)
                cert = os.environ.get("HOME_OPS_KUBERNETES_CLIENT_CERT_FILE") if kube else None
                if cert:
                    context.load_cert_chain(cert, os.environ.get("HOME_OPS_KUBERNETES_CLIENT_KEY_FILE"))
                opener = urllib.request.build_opener(
                    urllib.request.ProxyHandler({}), NoRedirect(), urllib.request.HTTPSHandler(context=context))
            except (OSError, ssl.SSLError, ValueError):
                raise CollectionError("TLS configuration unavailable") from None
            setattr(self, attr, opener)
        return opener

    def get(self, kube, path, params, deadline):
        headers = {"Accept": "application/json"}
        if kube and not os.environ.get("HOME_OPS_KUBERNETES_CLIENT_CERT_FILE"):
            try:
                with open(self.token_file, encoding="utf-8") as stream:
                    token = stream.read(65537).strip()
                if not token or len(token) > 65536 or "\n" in token or "\r" in token:
                    raise CollectionError("service-account token unavailable")
                headers["Authorization"] = "Bearer " + token
            except OSError:
                # A deliberately configured loopback proxy does not need a token.
                if urllib.parse.urlsplit(self.kube_url).hostname not in ("localhost", "127.0.0.1", "::1"):
                    raise CollectionError("service-account token unavailable") from None
        url = (self.kube_url if kube else self.prom_url).rstrip("/") + path
        if params:
            url += "?" + urllib.parse.urlencode(params, doseq=True)
        request = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with self._opener(kube).open(request, timeout=remaining(deadline)) as response:
                # read1 returns promptly even on trickling responses; check the total deadline.
                chunks, size = [], 0
                while True:
                    timeout = remaining(deadline)
                    # urllib's socket timeout otherwise remains the original request
                    # timeout even after earlier chunks consumed most of the deadline.
                    if response.fp is not None:
                        response.fp.raw._sock.settimeout(timeout)
                    chunk = response.read1(min(65536, MAX_RESPONSE_BYTES + 1 - size))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    size += len(chunk)
                    if size > MAX_RESPONSE_BYTES:
                        raise ResponseTooLarge("response exceeds bounded read size")
                remaining(deadline)
                payload = json.loads(b"".join(chunks))
        except urllib.error.HTTPError as exc:
            raise CollectionError("HTTP status " + str(exc.code)) from None
        except (urllib.error.URLError, OSError, TimeoutError):
            raise CollectionError("network or TLS request failed") from None
        except (ValueError, UnicodeError):
            raise CollectionError("invalid JSON response") from None
        if not isinstance(payload, dict):
            raise CollectionError("JSON response is not an object")
        return payload

    def kube_items(self, path, deadline, params=None):
        query = dict(params or {})
        query["limit"] = 50
        resource_version = None
        previous_token = None
        narrowed = False
        while True:
            try:
                page = self.get(True, path, query, deadline)
            except ResponseTooLarge:
                if narrowed:
                    raise
                query["limit"] = 1
                narrowed = True
                page = self.get(True, path, query, deadline)
            metadata = page.get("metadata")
            items = page.get("items")
            if not isinstance(metadata, dict) or not isinstance(items, list):
                raise CollectionError("invalid Kubernetes list response")
            rv = metadata.get("resourceVersion")
            if not isinstance(rv, str) or not rv:
                raise CollectionError("Kubernetes list resourceVersion missing")
            if resource_version is not None and resource_version != rv:
                raise CollectionError("Kubernetes pagination resourceVersion changed")
            resource_version = rv
            for item in items:
                remaining(deadline)
                if not isinstance(item, dict):
                    raise CollectionError("invalid Kubernetes list item")
                yield item
            token = metadata.get("continue", "")
            if not isinstance(token, str):
                raise CollectionError("invalid Kubernetes continuation token")
            if not token:
                if metadata.get("remainingItemCount", 0):
                    raise CollectionError("Kubernetes pagination ended prematurely")
                break
            if token == previous_token or not items:
                raise CollectionError("Kubernetes pagination made no progress")
            previous_token = token
            query["continue"] = token

    def _prom(self, path, params, deadline):
        payload = self.get(False, path, params, deadline)
        if (payload.get("status") != "success" or payload.get("warnings") or payload.get("isPartial")
                or payload.get("total_pages", 1) > 1):
            raise CollectionError("Prometheus response failed or incomplete")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise CollectionError("invalid Prometheus data")
        return data

    def prom_query(self, expression, deadline):
        data = self._prom("/api/v1/query", {"query": expression, "deny_partial_response": "1"}, deadline)
        if data.get("resultType") != "vector" or not isinstance(data.get("result"), list):
            raise CollectionError("expected Prometheus instant vector")
        return data["result"]

    def rules(self, name, group, deadline):
        data = self._prom("/api/v1/rules", {"type": "alert", "rule_name[]": name,
                                         "rule_group[]": group, "exclude_alerts": "true"}, deadline)
        groups = data.get("groups")
        if not isinstance(groups, list) or data.get("groupNextToken") or data.get("nextToken"):
            raise CollectionError("rules response invalid or truncated")
        return groups


def text(value, maximum=180):
    """Names/identifiers only: no upstream errors, object bodies or expressions."""
    return re.sub(r"[^a-zA-Z0-9_.:/@+ -]", "?", str(value))[:maximum]


def stamp(value):
    if not isinstance(value, str):
        raise CollectionError("required timestamp missing")
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
        return parsed.timestamp()
    except ValueError:
        raise CollectionError("invalid timestamp") from None


def number(value):
    try:
        result = float(value)
    except (ValueError, TypeError):
        raise CollectionError("invalid numeric sample") from None
    if not math.isfinite(result):
        raise CollectionError("non-finite numeric sample")
    return result


def samples(rows):
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("metric"), dict):
            raise CollectionError("invalid metric sample")
        value = row.get("value")
        if not isinstance(value, list) or len(value) != 2:
            raise CollectionError("invalid instant sample")
        yield row["metric"], number(value[1])


def identity(obj):
    metadata = obj.get("metadata", {})
    if not metadata.get("name"):
        raise CollectionError("resource identity missing")
    return {"name": text(metadata["name"], 253), "namespace": text(metadata.get("namespace", ""), 63)}


def representative(obj, phase=None, started=None, ended=None):
    row = identity(obj)
    row.update(phase=text(phase or "unknown", 40), started=text(started, 40) if started else None,
               ended=text(ended, 40) if ended else None)
    return row


class Category:
    def __init__(self, name):
        self.data = {"category": name, "evaluated_count": 0, "coverage_complete": False,
                     "finding_count": 0, "error_count": 0, "representatives": []}

    def finding(self, reason, row=None):
        self.data["finding_count"] += 1
        self.example(reason, row)

    def example(self, reason, row=None):
        if len(self.data["representatives"]) < 2:
            self.data["representatives"].append({"reason": reason, **(row or {})})

    def error(self, reason="required evidence unavailable", row=None):
        self.data["error_count"] += 1
        self.example(reason, row)

    def finish(self):
        self.data["status"] = ("error" if self.data["error_count"] or not self.data["coverage_complete"]
                               else "fail" if self.data["finding_count"] else "pass")
        return self.data


def run_category(name, action):
    category = Category(name)
    try:
        action(category)
        category.data["coverage_complete"] = not bool(category.data["error_count"])
    except CollectionError as exc:
        # CollectionError messages are fixed strings created by this module.
        category.error(str(exc))
    except Exception:
        category.error("unexpected collector response shape")
    return category.finish()


def cnpg(category, reader, deadline, now):
    latest = []
    for obj in reader.kube_items(CNPG, deadline):
        cluster = obj.get("spec", {}).get("cluster", {}).get("name")
        if cluster != "postgres":
            if not cluster and obj.get("metadata", {}).get("name", "").startswith("postgres-"):
                category.error("postgres-named backup cluster ownership missing", identity(obj))
            continue
        category.data["evaluated_count"] += 1
        status = obj.get("status", {})
        row = representative(obj, status.get("phase"), status.get("startedAt"), status.get("stoppedAt"))
        try:
            started = stamp(status.get("startedAt"))
        except CollectionError:
            category.error("backup STARTED missing or invalid", row)
            continue
        latest.append((started, row, bool(status.get("error"))))
        latest.sort(key=lambda entry: (entry[0], entry[1]["name"]), reverse=True)
        del latest[2:]
    category.data["latest_runs"] = [entry[1] for entry in latest]
    if len(latest) < 2 and not category.data["error_count"]:
        category.finding("fewer than two postgres backup runs")
    for started, row, has_error in latest:
        if row["phase"] != "completed" or has_error:
            category.finding("latest backup is not completed without error")
        if started > now + 300:
            category.error("backup STARTED is in the future", row)
    # Daily at 16:00 UTC: 36h tolerates the next scheduled run finishing;
    # the preceding daily run must also be within the last 60h.
    for index, (started, row, _) in enumerate(latest):
        if now - started > (36 + 24 * index) * 3600:
            category.finding("expected daily backup run is stale")


def cron_config(category, reader, deadline, now, state):
    found = False
    for obj in reader.kube_items(CRON, deadline, {"fieldSelector": "metadata.name=postgres-backup-verify"}):
        if obj.get("metadata", {}).get("name") != "postgres-backup-verify":
            continue
        category.data["evaluated_count"] += 1
        if found:
            raise CollectionError("duplicate verification CronJob")
        found = True
        state["created"] = stamp(obj.get("metadata", {}).get("creationTimestamp"))
        state["uid"] = obj.get("metadata", {}).get("uid")
        spec, status = obj.get("spec", {}), obj.get("status", {})
        row = identity(obj)
        row.update(schedule=text(spec.get("schedule"), 80),
                   last_schedule=text(status.get("lastScheduleTime"), 40))
        category.example("weekly verification target; success requires owned Job evidence", row)
        if spec.get("schedule") != "0 4 * * 0":
            category.error("verification CronJob schedule is not the configured weekly cadence")
        if spec.get("suspend", False):
            category.finding("verification CronJob is suspended", row)
        if not state["uid"]:
            category.error("verification CronJob UID missing")
    if not found:
        category.finding("verification CronJob not found")


def owned_jobs(category, reader, deadline, now, state):
    latest, newest_success = None, None
    for obj in reader.kube_items(JOBS, deadline):
        owners = obj.get("metadata", {}).get("ownerReferences", [])
        if not any(owner.get("kind") == "CronJob" and owner.get("name") == "postgres-backup-verify"
                   and (not state.get("uid") or owner.get("uid") == state["uid"]) for owner in owners):
            continue
        category.data["evaluated_count"] += 1
        status = obj.get("status", {})
        try:
            created = stamp(obj.get("metadata", {}).get("creationTimestamp"))
        except CollectionError:
            category.error("owned verification Job CREATED missing or invalid", identity(obj))
            continue
        failed = any(c.get("type") == "Failed" and c.get("status") == "True"
                     for c in status.get("conditions", []))
        succeeded = number(status.get("succeeded", 0) or 0) > 0
        failed = failed or (not succeeded and number(status.get("failed", 0) or 0) > 0 and not status.get("active"))
        phase = "Failed" if failed else "Succeeded" if succeeded else "Running" if status.get("active") else "Pending"
        row = representative(obj, phase, status.get("startTime"), status.get("completionTime"))
        row["created"] = text(obj["metadata"]["creationTimestamp"], 40)
        if not any(field in status for field in ("succeeded", "failed", "active", "startTime", "conditions")):
            category.error("owned verification Job execution status missing", row)
        if latest is None or (created, row["name"]) > (latest[0], latest[1]["name"]):
            latest = (created, row)
        if succeeded:
            try:
                completion = stamp(status.get("completionTime"))
            except CollectionError:
                category.error("successful verification Job completion missing or invalid", row)
                continue
            if completion > now + 300:
                category.error("verification completion is in the future", row)
            newest_success = max(newest_success or completion, completion)
    if not state.get("uid"):
        category.error("CronJob ownership could not be verified")
    if latest:
        category.data["latest_run"] = latest[1]
        if latest[1]["phase"] == "Failed":
            category.finding("latest owned verification Job failed", latest[1])
    if (not category.data["error_count"] and state.get("uid")
            and (newest_success is None or now - newest_success > 10 * 86400)):
        created = state.get("created")
        if newest_success is None and created is not None and 0 <= now - created < 10 * 86400:
            category.example("new weekly target has not reached the 10-day missing-success deadline")
        else:
            category.finding("no successful owned Job completion within 10 days")
    category.data["newest_success_age_seconds"] = round(now - newest_success) if newest_success else None


def metric_map(reader, expression, label, deadline):
    result = {}
    for labels, value in samples(reader.prom_query(expression, deadline)):
        namespace, name = labels.get("namespace"), labels.get(label)
        if not isinstance(namespace, str) or not isinstance(name, str) or not name:
            raise CollectionError("policy metric identity missing")
        key = (namespace, name)
        if key in result:
            raise CollectionError("duplicate aggregated policy metric")
        result[key] = value
    return result


def policies(category, reader, deadline, now):
    successes = metric_map(reader, SUCCESS_METRIC, "policy", deadline)
    failures = metric_map(reader, FAILURE_METRIC, "name", deadline)
    oldest_age = None
    for obj in reader.kube_items(KOPIUR + "snapshotpolicies", deadline):
        category.data["evaluated_count"] += 1
        row = identity(obj)
        key = (obj["metadata"].get("namespace", ""), obj["metadata"]["name"])
        success, failure = successes.pop(key, None), failures.pop(key, None)
        if success is None or failure is None:
            category.error("policy success or consecutive-failure metric missing", row)
            continue
        age = now - success
        oldest_age = max(oldest_age if oldest_age is not None else age, age)
        row.update(success_age_seconds=round(age), consecutive_failures=failure)
        # The deployed policies run every six hours and expose no freshness SLA
        # field; the fixed backup check uses a 24-hour success deadline.
        if success <= 0 or age > 86400:
            category.finding("policy has no successful snapshot within 24 hours", row)
        elif age < -300:
            category.error("policy success metric is in the future", row)
        if failure < 0:
            category.error("negative consecutive-failure metric", row)
        elif failure > 0:
            category.finding("policy has consecutive failed snapshots", row)
    category.data["oldest_success_age_seconds"] = round(oldest_age) if oldest_age is not None else None
    if not category.data["evaluated_count"]:
        category.error("no SnapshotPolicies discovered")
    category.data["unmatched_success_metric_count"] = len(successes)
    category.data["unmatched_failure_metric_count"] = len(failures)
    if successes or failures:
        category.error("policy metrics do not match discovered policies")


def repository(category, reader, deadline, now):
    found = False
    for obj in reader.kube_items(KOPIUR + "clusterrepositories", deadline, {"fieldSelector": "metadata.name=nas"}):
        if obj.get("metadata", {}).get("name") != "nas":
            continue
        found = True
        category.data["evaluated_count"] += 1
        status = obj.get("status", {})
        conditions = {c.get("type"): c.get("status") for c in status.get("conditions", [])}
        row = representative(obj, status.get("phase"))
        row.update(ready=text(conditions.get("Ready"), 16),
                   backend_reachable=text(conditions.get("BackendReachable"), 16))
        category.example("nas repository readiness", row)
        for key in ("Ready", "BackendReachable"):
            if key not in conditions:
                category.error("repository " + key + " condition missing", row)
            elif conditions[key] == "False":
                category.finding("repository " + key + " is False", row)
            elif conditions[key] != "True":
                category.error("repository " + key + " is unknown", row)
        if not status.get("phase"):
            category.error("repository phase missing", row)
        elif status["phase"] != "Ready":
            category.finding("repository phase is not Ready", row)
    if not found:
        category.finding("nas repository not found")


def snapshots(category, reader, deadline, now):
    counts = {"running_pending": 0, "running_pending_over_30m": 0,
              "running_pending_missing_started": 0, "failed_recent": 0, "queued_for_repository": 0}
    category.data.update(counts)
    counts = category.data
    oldest, newest_failed = None, None
    for obj in reader.kube_items(KOPIUR + "snapshots", deadline):
        category.data["evaluated_count"] += 1
        status = obj.get("status", {})
        phase = status.get("phase")
        timing = status.get("timing") or {}
        started, ended = timing.get("startTime"), timing.get("endTime")
        if phase in ("Running", "Pending"):
            counts["running_pending"] += 1
            if any(c.get("type") == "RepositorySlotAvailable" and c.get("status") == "False"
                   for c in status.get("conditions", [])):
                counts["queued_for_repository"] += 1
            if started is None:
                counts["running_pending_missing_started"] += 1
                continue
            try:
                start = stamp(started)
            except CollectionError:
                category.error("snapshot STARTED invalid", identity(obj))
                continue
            if start > now + 300:
                category.error("snapshot STARTED is in the future", identity(obj))
            elif now - start > 1800:
                counts["running_pending_over_30m"] += 1
                category.data["finding_count"] += 1
                row = representative(obj, phase, started, ended)
                if oldest is None or start < oldest[0]:
                    oldest = (start, row)
        elif phase == "Failed":
            try:
                end = stamp(ended if ended is not None else obj.get("metadata", {}).get("creationTimestamp"))
            except CollectionError:
                category.error("Failed snapshot ENDED/CREATED missing or invalid", identity(obj))
                continue
            if end >= now - 48 * 3600:
                counts["failed_recent"] += 1
                category.data["finding_count"] += 1
                row = representative(obj, phase, started, ended)
                row["created"] = text(obj.get("metadata", {}).get("creationTimestamp"), 40)
                if newest_failed is None or end > newest_failed[0]:
                    newest_failed = (end, row)
        elif phase not in ("Succeeded", "Discovered", "Unchanged", "Deleting"):
            category.error("snapshot phase missing or unsupported", identity(obj))
    if counts["running_pending_over_30m"]:
        category.example("Running/Pending STARTED more than 30 minutes ago", oldest[1])
    if counts["failed_recent"]:
        category.example("Failed ENDED within 48 hours (CREATED fallback only if ENDED missing)", newest_failed[1])


def result(name, categories):
    errors = sum(c["error_count"] for c in categories)
    findings = sum(c["finding_count"] for c in categories)
    status = "error" if errors or any(not c["coverage_complete"] for c in categories) else "fail" if findings else "pass"
    return {"status": status, "message": name + ": " + status,
            "rationale": json.dumps({"categories": categories}, separators=(",", ":"), ensure_ascii=True),
            "error": "one or more categories could not be completely evaluated" if status == "error" else None,
            "model_used": None, "notifications": []}


def backup(reader, deadline, now):
    state = {}
    categories = [run_category("cnpg_daily_runs", lambda c: cnpg(c, reader, deadline, now)),
                  run_category("weekly_cronjob", lambda c: cron_config(c, reader, deadline, now, state)),
                  run_category("weekly_owned_jobs", lambda c: owned_jobs(c, reader, deadline, now, state)),
                  run_category("kopiur_policies", lambda c: policies(c, reader, deadline, now)),
                  run_category("nas_repository", lambda c: repository(c, reader, deadline, now)),
                  run_category("kopiur_snapshots", lambda c: snapshots(c, reader, deadline, now))]
    return result(BACKUP, categories)


def resolved(reader, deadline):
    category = Category("resolved_alert_rules")
    evidence = []
    candidates = set()
    category.data.update(healed_count=0, omitted_rule_evidence_count=0)

    def remember(row):
        # Evaluation is exhaustive; only the displayed failure evidence is capped.
        if len(evidence) < 8:
            evidence.append(row)
        else:
            category.data["omitted_rule_evidence_count"] += 1

    try:
        for labels, _ in samples(reader.prom_query(CANDIDATES, deadline)):
            name, group = labels.get("alertname"), labels.get("alertgroup")
            if not isinstance(name, str) or not name or not isinstance(group, str) or not group:
                raise CollectionError("candidate alert name/group missing")
            candidates.add((name, group))
        category.data["candidate_count"] = len(candidates)
        for name, group_name in sorted(candidates):
            matched = 0
            try:
                groups = reader.rules(name, group_name, deadline)
                for group_index, group in enumerate(groups):
                    if not isinstance(group, dict):
                        raise CollectionError("invalid rule group")
                    if group.get("name") != group_name:
                        continue
                    rules = group.get("rules")
                    if not isinstance(rules, list):
                        raise CollectionError("matching group rules missing")
                    for rule_index, rule in enumerate(rules):
                        if not isinstance(rule, dict):
                            raise CollectionError("invalid rule response")
                        if rule.get("name") != name or rule.get("type", "alerting") != "alerting":
                            continue
                        matched += 1
                        category.data["evaluated_count"] += 1
                        source = str(group.get("file", ""))
                        # Index is preserved even when a server returns duplicate name/group rules.
                        stable_input = [source, group_name, str(group.get("id", "")), str(rule.get("id", "")), rule_index]
                        stable = hashlib.sha256(json.dumps(stable_input).encode()).hexdigest()[:20]
                        row = {"name": text(name, 253), "group": text(group_name, 253),
                               "file": text(source, 180), "group_id": text(group.get("id", ""), 80),
                               "rule_id": text(rule.get("id", ""), 80),
                               "stable_id": stable, "group_index": group_index, "rule_index": rule_index,
                               "numeric_result": None}
                        datasource = rule.get("datasourceType", group.get("type", "prometheus"))
                        if datasource != "prometheus":
                            row["status"] = "unevaluated"
                            category.error("matching rule uses a non-Prometheus datasource")
                            remember(row)
                            continue
                        expression = rule.get("query", rule.get("expr"))
                        if not isinstance(expression, str) or not expression.strip():
                            row["status"] = "error"
                            category.error("matching rule expression missing")
                            remember(row)
                            continue
                        try:
                            values = list(samples(reader.prom_query("sum(absent(" + expression + ")) or vector(0)", deadline)))
                            if len(values) != 1 or values[0][1] not in (0, 1):
                                raise CollectionError("absent query must return exactly one numeric 0 or 1")
                            value = int(values[0][1])
                            row["numeric_result"] = value
                            row["status"] = "pass" if value == 1 else "fail"
                            if value == 1:
                                category.data["healed_count"] += 1
                            else:
                                remember(row)
                                category.finding("matching rule has not healed")
                        except Exception:
                            row["status"] = "error"
                            category.error("matching rule evaluation failed")
                            remember(row)
                if not matched:
                    category.error("candidate has no matching alert rule", {"name": text(name), "group": text(group_name)})
            except Exception:
                category.error("candidate rule discovery failed", {"name": text(name), "group": text(group_name)})
        category.data["coverage_complete"] = not bool(category.data["error_count"])
    except Exception:
        category.error("candidate collection failed")
    data = result(RESOLVED, [category.finish()])
    data["rationale"] = json.dumps({"categories": [category.data], "rule_evaluations": evidence}, separators=(",", ":"))
    return data


def collect_with_reader(query, deadline, reader, now=None):
    if query == BACKUP:
        return backup(reader, deadline, time.time() if now is None else now)
    if query == RESOLVED:
        return resolved(reader, deadline)
    return None


def collect(query: str, deadline: float) -> dict | None:
    if query not in (BACKUP, RESOLVED):
        return None
    try:
        return collect_with_reader(query, deadline, Reader())
    except Exception:
        return {"status": "error", "message": query + ": error", "rationale": "collector configuration unavailable",
                "error": "collector configuration unavailable", "model_used": None, "notifications": []}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", choices=(BACKUP, RESOLVED))
    parser.add_argument("--timeout", type=float, default=300)
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("timeout must be positive and finite")
    outcome = collect(args.query, time.monotonic() + args.timeout)
    print(json.dumps(outcome, ensure_ascii=True))
    return {"pass": 0, "fail": 1, "error": 2}[outcome["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
