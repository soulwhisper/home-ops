# SPDX-License-Identifier: Apache-2.0
"""Isolated behavioral regressions; stdlib only, no cluster or model access.

Run: python -m unittest discover -s .github/scripts -p test_healthcheck_deadline.py
"""

import asyncio
import copy
from enum import Enum
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[2]
PATCHES = ROOT / "kubernetes/apps/monitoring-system/robusta/app/scripts"


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, PATCHES / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Status(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"


class Response:
    def __init__(self, status="pass", message="Healthy", duration=0.01, **kwargs):
        self.status = Status(status)
        self.message = message
        self.duration = duration
        self.error = kwargs.get("error")
        self.values = dict(rationale=None, model_used=None, notifications=None, **kwargs)

    def model_dump(self, **kwargs):
        return dict(self.values, status=self.status.value, message=self.message,
                    duration=self.duration, error=self.error)


class Spec:
    def __init__(self, query, timeout=30, mode="monitor", destinations=None, model=None):
        if not query or timeout < 1:
            raise ValueError("invalid")
        self.query, self.timeout, self.model = query, timeout, model
        self.mode = types.SimpleNamespace(value=mode)
        self.destinations = destinations or []


class APIError(Exception):
    def __init__(self, status):
        self.status = status


class MemoryAPI:
    """Enforce real status-subresource replacement and UID/RV compare-and-swap."""
    def __init__(self):
        self.resource = dict(apiVersion="holmesgpt.dev/v1alpha1", kind="HealthCheck",
                             metadata=dict(name="check", namespace="ns", uid="uid", resourceVersion="1"),
                             spec=dict(query="is healthy", timeout=5), status={})
        self.writes = []
        self.conflicts = 0
        self.fail_terminal = False

    def get_namespaced_custom_object(self, **kwargs):
        return copy.deepcopy(self.resource)

    def replace_namespaced_custom_object_status(self, body, **kwargs):
        if self.conflicts:
            self.conflicts -= 1
            raise APIError(409)
        if body["metadata"]["uid"] != self.resource["metadata"]["uid"]:
            raise APIError(409)
        if body["metadata"]["resourceVersion"] != self.resource["metadata"]["resourceVersion"]:
            raise APIError(409)
        if self.fail_terminal and body["status"]["phase"] != "Running":
            raise APIError(503)
        self.resource["status"] = copy.deepcopy(body["status"])
        self.resource["metadata"]["resourceVersion"] = str(int(self.resource["metadata"]["resourceVersion"]) + 1)
        self.writes.append(copy.deepcopy(body["status"]))
        return copy.deepcopy(self.resource)


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.runtime = load("deadline_runtime", "holmes-check-runtime.py")
        self.temp = tempfile.TemporaryDirectory()
        self.pids = Path(self.temp.name) / "pids.json"

    def tearDown(self):
        # Even an assertion failure must not leave a blocking test process.
        if self.pids.exists():
            for pid in json.loads(self.pids.read_text()):
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        self.temp.cleanup()

    def blocking_command(self):
        child = "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(60)"
        script = ("import subprocess,sys,signal,time,os,json,pathlib; "
                  "signal.signal(signal.SIGTERM,signal.SIG_IGN); "
                  f"child=subprocess.Popen([sys.executable,'-c',{child!r}]); "
                  f"pathlib.Path({str(self.pids)!r}).write_text(json.dumps([os.getpid(),child.pid])); "
                  "time.sleep(60)")
        return [sys.executable, "-c", script]

    async def wait_started(self):
        until = time.monotonic() + 5
        while not self.pids.exists():
            if time.monotonic() > until:
                self.fail("worker never started")
            await asyncio.sleep(0.01)

    def assert_reaped(self):
        self.assertTrue(self.pids.exists())
        for pid in json.loads(self.pids.read_text()):
            self.assertFalse(Path(f"/proc/{pid}").exists(), f"process {pid} survived or remained a zombie")

    async def test_deadline_kills_and_reaps_blocked_worker_and_child(self):
        result = await self.runtime.run_worker({}, time.monotonic() + 0.6,
                                               command=self.blocking_command())
        self.assertEqual(result["status"], "error")
        self.assertIn("DeadlineExceeded", result["error"])
        self.assert_reaped()

    async def test_elapsed_budget_is_not_restarted(self):
        deadline = time.monotonic() + 0.6
        await asyncio.sleep(0.4)
        script = ("import os,time,json; time.sleep(.4); "
                  "f=os.fdopen(int(os.environ['HOME_OPS_CHECK_RESULT_FD']),'w'); "
                  "json.dump({'status':'pass'},f); f.close()")
        result = await self.runtime.run_worker({}, deadline,
                                               command=[sys.executable, "-c", script])
        self.assertIn("DeadlineExceeded", result["error"])

    async def test_disconnect_cleans_entire_group(self):
        disconnected = False
        async def is_disconnected():
            return disconnected
        task = asyncio.create_task(self.runtime.run_worker(
            {}, time.monotonic() + 20, is_disconnected, self.blocking_command()))
        try:
            await self.wait_started()
            disconnected = True
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assert_reaped()
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    async def test_task_cancellation_also_cleans_entire_group(self):
        task = asyncio.create_task(self.runtime.run_worker(
            {}, time.monotonic() + 20, command=self.blocking_command()))
        try:
            await self.wait_started()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assert_reaped()
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
    async def test_exited_group_skips_cleanup_grace(self):
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-c", "pass", start_new_session=True)
        await process.wait()
        with patch.object(self.runtime.asyncio, "sleep", new=AsyncMock()) as sleep:
            await self.runtime._stop_group(process)
        sleep.assert_not_awaited()


class ClientTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        class RequestError(Exception):
            pass
        class HTTPStatusError(Exception):
            pass
        self.http = types.ModuleType("httpx")
        self.http.RequestError = RequestError
        self.http.HTTPStatusError = HTTPStatusError
        self.http.Timeout = lambda *args, **kwargs: types.SimpleNamespace(args=args, **kwargs)
        self.http.Limits = lambda **kwargs: None
        self.http.AsyncHTTPTransport = lambda **kwargs: None
        self.transport = types.SimpleNamespace(post=AsyncMock(), aclose=AsyncMock())
        self.http.AsyncClient = lambda **kwargs: self.transport
        models = types.ModuleType("holmes_operator.models")
        models.CheckResponse = Response
        with patch.dict(sys.modules, {"httpx": self.http, "holmes_operator.models": models}):
            self.module = load("deadline_client", "holmes-operator-api-client-0.45.0.py")
        self.client = self.module.HolmesAPIClient("http://api", timeout=300)

    async def execute(self, **kwargs):
        return await self.client.execute_check("check", "question", mode="monitor",
                                               destinations=[], **kwargs)

    async def test_network_failure_is_nonempty_typed_and_posts_once(self):
        self.transport.post.side_effect = self.http.RequestError()
        with self.assertRaises(self.module.HolmesExecutionError) as caught:
            await self.execute(timeout=5)
        self.assertIn("RequestError", str(caught.exception))
        self.assertIn("not replayed", str(caught.exception))
        self.assertEqual(self.transport.post.await_count, 1)

    async def test_expired_budget_never_posts(self):
        with self.assertRaises(self.module.HolmesExecutionError):
            await self.execute(timeout=5, deadline_unix=time.time() - 1)
        self.transport.post.assert_not_awaited()

    async def test_deadline_and_http_budget_use_same_remaining_time(self):
        reply = types.SimpleNamespace(raise_for_status=lambda: None,
                                      json=lambda: dict(status="pass", message="ok", duration=.1))
        self.transport.post.return_value = reply
        deadline = time.time() + .5
        await self.execute(timeout=300, deadline_unix=deadline, execution_id="uid/run")
        sent = self.transport.post.call_args.kwargs
        self.assertEqual(sent["json"]["deadline_unix"], deadline)
        self.assertEqual(sent["json"]["execution_id"], "uid/run")
        self.assertLessEqual(sent["timeout"].args[0], .5 + self.module.RESPONSE_GRACE)

    async def test_total_http_timeout_is_not_per_read_or_retried(self):
        async def blocked(*args, **kwargs):
            await asyncio.sleep(30)
        self.transport.post.side_effect = blocked
        self.module.RESPONSE_GRACE = .01
        with self.assertRaises(self.module.HolmesExecutionError) as caught:
            await self.execute(timeout=.03)
        self.assertIn("TimeoutError", str(caught.exception))
        self.assertEqual(self.transport.post.await_count, 1)


class HandlerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        class TemporaryError(Exception):
            def __init__(self, message, **kwargs):
                super().__init__(message)
        self.kopf = types.ModuleType("kopf")
        self.kopf.TemporaryError = TemporaryError
        self.kopf.Logger = object
        self.kopf.on = types.SimpleNamespace(**{name: lambda *a, **kw: lambda f: f
                                                for name in ("create", "update", "resume")})
        context = types.ModuleType("holmes_operator.context")
        self.api = MemoryAPI()
        self.client = types.SimpleNamespace(execute_check=AsyncMock(return_value=Response()))
        context.k8s_api, context.api_client = self.api, self.client
        package = types.ModuleType("holmes_operator")
        package.context = context
        models = types.ModuleType("holmes_operator.models")
        models.HealthCheckSpec = Spec
        client_module = types.ModuleType("holmes_operator.client.holmes_api_client")
        client_module.HolmesExecutionError = type("HolmesExecutionError", (RuntimeError,), {})
        with patch.dict(sys.modules, {"kopf": self.kopf, "holmes_operator": package,
                                     "holmes_operator.context": context,
                                     "holmes_operator.client.holmes_api_client": client_module,
                                     "holmes_operator.models": models}):
            self.handler = load("deadline_handler", "holmes-operator-healthcheck-0.45.0.py")

    async def create(self):
        await self.handler.on_healthcheck_create({}, "check", "ns", "uid", None)

    def assert_terminal_consistent(self, phase, condition):
        status = self.api.resource["status"]
        self.assertEqual(status["phase"], phase)
        types_ = [c["type"] for c in status["conditions"]]
        self.assertEqual(types_, ["Execution", condition])
        self.assertNotIn("Running", types_)
        self.assertIn("completionTime", status)
        return status

    async def test_failure_is_single_terminal_write_and_not_reexecuted(self):
        self.client.execute_check.side_effect = TimeoutError()
        await self.create()
        status = self.assert_terminal_consistent("Failed", "Failed")
        self.assertIn("TimeoutError", status["error"])
        await self.create()
        self.assertEqual(self.client.execute_check.await_count, 1)
        self.assertEqual([s["phase"] for s in self.api.writes], ["Running", "Failed"])

    async def test_status_conflicts_retry_storage_not_execution(self):
        self.api.conflicts = 2
        await self.create()
        self.assert_terminal_consistent("Completed", "Complete")
        self.assertEqual(self.client.execute_check.await_count, 1)

    async def test_terminal_storage_failure_reuses_cached_result(self):
        self.api.fail_terminal = True
        with self.assertRaises(self.kopf.TemporaryError):
            await self.create()
        self.assertEqual(self.api.resource["status"]["phase"], "Running")
        self.api.fail_terminal = False
        await self.create()
        self.assert_terminal_consistent("Completed", "Complete")
        self.assertEqual(self.client.execute_check.await_count, 1)

    async def test_existing_running_uid_is_not_investigated_again(self):
        self.api.resource["status"] = dict(phase="Running", startTime="old")
        await self.create()
        self.client.execute_check.assert_not_awaited()
        await self.handler.on_healthcheck_resume("check", "ns", "uid")
        status = self.api.resource["status"]
        self.assertEqual(status["phase"], "Failed")
        self.assertIn("ExecutionInterrupted", status["error"])
        self.client.execute_check.assert_not_awaited()

    async def test_explicit_rerun_replaces_old_terminal_and_is_idempotent(self):
        self.client.execute_check.side_effect = TimeoutError()
        await self.create()
        old = copy.deepcopy(self.api.resource)
        self.api.resource["metadata"]["annotations"] = {"holmesgpt.dev/rerun": "true"}
        new = copy.deepcopy(self.api.resource)
        self.client.execute_check.side_effect = None
        self.client.execute_check.return_value = Response()
        await self.handler.on_healthcheck_update(old, new, "check", "ns", None)
        status = self.assert_terminal_consistent("Completed", "Complete")
        self.assertNotIn("error", status)
        await self.handler.on_healthcheck_update(old, new, "check", "ns", None)
        self.assertEqual(self.client.execute_check.await_count, 2)

    async def test_late_result_cannot_overwrite_new_execution(self):
        first_entered, release = asyncio.Event(), asyncio.Event()
        async def response(**kwargs):
            if not first_entered.is_set():
                first_entered.set()
                await release.wait()
                return Response(status="fail", message="late old result")
            return Response(message="rerun result")
        self.client.execute_check.side_effect = response
        original = asyncio.create_task(self.create())
        try:
            await first_entered.wait()
            old = copy.deepcopy(self.api.resource)
            self.api.resource["metadata"]["annotations"] = {"holmesgpt.dev/rerun": "true"}
            new = copy.deepcopy(self.api.resource)
            await self.handler.on_healthcheck_update(old, new, "check", "ns", None)
            release.set()
            await original
            self.assertEqual(self.api.resource["status"]["message"], "rerun result")
            self.assert_terminal_consistent("Completed", "Complete")
        finally:
            release.set()
            await asyncio.gather(original, return_exceptions=True)

    async def test_deleted_recreated_uid_rejects_late_write(self):
        async def replace_resource(**kwargs):
            self.api.resource["metadata"].update(uid="new-uid", resourceVersion="1")
            self.api.resource["status"] = {}
            return Response(message="stale")
        self.client.execute_check.side_effect = replace_resource
        await self.create()
        self.assertEqual(self.api.resource["status"], {})

    async def test_rerun_retry_uses_kopf_start_time_not_changed_resource_version(self):
        await self.create()
        old = copy.deepcopy(self.api.resource)
        self.api.resource["metadata"]["annotations"] = {"holmesgpt.dev/rerun": "true"}
        new = copy.deepcopy(self.api.resource)
        from datetime import datetime, timezone
        started = datetime.now(timezone.utc)
        await self.handler.on_healthcheck_update(old, new, "check", "ns", None, started=started)
        changed = copy.deepcopy(self.api.resource)
        await self.handler.on_healthcheck_update(old, changed, "check", "ns", None,
                                                started=started, retry=1)
        self.assertEqual(self.client.execute_check.await_count, 2)

    async def test_uncertain_claim_write_never_posts_on_retry(self):
        replace = self.api.replace_namespaced_custom_object_status
        uncertain = True
        def lose_response(**kwargs):
            nonlocal uncertain
            result = replace(**kwargs)
            if uncertain:
                uncertain = False
                raise APIError(503)
            return result
        self.api.replace_namespaced_custom_object_status = lose_response
        with self.assertRaises(self.kopf.TemporaryError):
            await self.create()
        await self.create()
        self.client.execute_check.assert_not_awaited()
        self.assert_terminal_consistent("Failed", "Failed")
    async def test_transform_programming_error_is_not_retried(self):
        def broken(resource):
            raise RuntimeError("transform bug")
        with self.assertRaisesRegex(RuntimeError, "transform bug"):
            await self.handler._status_change("check", "ns", "uid", broken)
        self.assertEqual(self.api.writes, [])

    async def test_validation_failure_has_field_detail_without_input_values(self):
        class InvalidSpec(Exception):
            def errors(self):
                return [{"loc": ("destinations", 0, "config", "integration_key"),
                         "type": "missing", "input": "DO-NOT-LOG"}]
        def invalid(**kwargs):
            raise InvalidSpec()
        self.handler.HealthCheckSpec = invalid
        self.api.resource["spec"] = {}
        logs = []
        logger = types.SimpleNamespace(warning=lambda *args: logs.append(args))
        await self.handler.on_healthcheck_create({}, "check", "ns", "uid", logger)
        status = self.assert_terminal_consistent("Failed", "Failed")
        self.assertIn("destinations/0/config/integration_key:missing", status["error"])
        self.assertNotIn("DO-NOT-LOG", status["error"])
        self.assertNotIn("DO-NOT-LOG", str(logs))


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.worker = load("deadline_worker", "holmes-check-worker.py")
        self.collector = load("worker_real_collectors", "collectors.py")
        self.payload = dict(request=dict(query="question", timeout=30, mode="monitor",
                                         model="configured-model", destinations=[]),
                            deadline=1234.0, config_file=None)

    def test_fixed_marker_never_initializes_config_or_model(self):
        self.payload["request"]["query"] = self.collector.RESOLVED
        self.payload["config_file"] = "/unreadable/config-source.yaml"
        config = types.ModuleType("holmes.config")
        class ForbiddenConfig:
            @classmethod
            def load_from_env(cls):
                raise AssertionError("fixed checks must not initialize the model")
        config.Config = ForbiddenConfig
        reader = types.SimpleNamespace(prom_query=lambda expression, deadline: [])
        with patch.dict(sys.modules, {"holmes.checks.collectors": self.collector,
                                     "holmes.config": config}), patch.object(self.collector, "Reader", return_value=reader):
            result = self.worker.execute(self.payload)
        self.assertEqual(result["status"], "pass")
        category = json.loads(result["rationale"])["categories"][0]
        self.assertEqual(category["candidate_count"], 0)
        self.assertTrue(category["coverage_complete"])

    def test_fixed_failure_preserves_verdict_and_dispatches_pagerduty_without_config(self):
        candidate = {"metric": {"alertname": "Alert", "alertgroup": "group"}, "value": [0, "1"]}
        zero = {"metric": {}, "value": [0, "0"]}
        def prom_query(expression, deadline):
            if expression == self.collector.CANDIDATES:
                return [candidate]
            if expression == "sum(absent(vector(1))) or vector(0)":
                return [zero]
            raise AssertionError("unexpected expression")
        reader = types.SimpleNamespace(
            prom_query=prom_query,
            rules=lambda name, group, deadline: [{"name": group, "type": "prometheus", "rules": [
                {"name": name, "type": "alerting", "query": "vector(1)"}]}])
        issues, deliveries = [], []
        def module(name, **attrs):
            result = types.ModuleType(name)
            result.__dict__.update(attrs)
            return result
        class Issue:
            def __init__(self, **kwargs):
                issues.append(kwargs)
        class LLMResult:
            def __init__(self, **kwargs):
                pass
        class PagerDuty:
            def __init__(self, integration_key):
                self.integration_key = integration_key
            def send_issue(self, issue, result):
                deliveries.append(self.integration_key)
        class ForbiddenConfig:
            @classmethod
            def load_from_env(cls):
                raise AssertionError("fixed failure must not load model config")
            @classmethod
            def load_from_file(cls, path):
                raise AssertionError("fixed failure must not load model config")
        modules = {
            "holmes.checks.collectors": self.collector,
            "holmes.config": module("holmes.config", Config=ForbiddenConfig),
            "holmes.core.issue": module("holmes.core.issue", Issue=Issue,
                                       IssueStatus=types.SimpleNamespace(OPEN="open")),
            "holmes.core.tool_calling_llm": module("holmes.core.tool_calling_llm", LLMResult=LLMResult),
            "holmes.plugins.destinations.pagerduty.plugin": module(
                "holmes.plugins.destinations.pagerduty.plugin", PagerDutyDestination=PagerDuty),
            "holmes.plugins.destinations.slack.plugin": module(
                "holmes.plugins.destinations.slack.plugin", SlackDestination=object),
        }
        self.payload["request"].update(
            query=self.collector.RESOLVED, mode="alert",
            destinations=[{"type": "pagerduty", "config": {"integration_key": "integration-key"}}])
        self.payload.update(config_file="/unreadable/config.yaml", cluster_name="main")
        with patch.dict(sys.modules, modules), patch.object(self.collector, "Reader", return_value=reader):
            result = self.worker.execute(self.payload)
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["notifications"], [{"type": "pagerduty", "status": "sent"}])
        self.assertEqual(deliveries, ["integration-key"])
        self.assertEqual(issues[0]["source_instance_id"], "main")


if __name__ == "__main__":
    unittest.main()
