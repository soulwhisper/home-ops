# SPDX-FileCopyrightText: HolmesGPT contributors
# SPDX-License-Identifier: Apache-2.0
"""Replacement for HolmesGPT 0.45.0 holmes_operator/handlers/healthcheck.py.

Claim before POST, publish the complete terminal status with UID/RV ownership,
and never replay an uncertain execution on a Kopf retry or operator restart.
"""

import asyncio
from datetime import datetime, timezone
import time
from typing import Any, Dict

import kopf

from holmes_operator import context
from holmes_operator.client.holmes_api_client import HolmesExecutionError
from holmes_operator.models import HealthCheckSpec

_GROUP = dict(group="holmesgpt.dev", version="v1alpha1", plural="healthchecks")
_ACTIVE = set()
_RESULTS = {}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _execution(status):
    return next((c for c in status.get("conditions", []) if c.get("type") == "Execution"), None)


async def _status_change(name, namespace, uid, transform):
    """Retry storage conflicts only; transform must never execute the check."""
    for attempt in range(5):
        try:
            resource = await asyncio.to_thread(
                context.k8s_api.get_namespaced_custom_object,
                **_GROUP, namespace=namespace, name=name, _request_timeout=(5, 10))
            if resource["metadata"]["uid"] != uid:
                return None
            replacement = transform(resource)
            if replacement is None:
                return None
            body = dict(resource, status=replacement)
            # PUT replaces all status fields together. UID/resourceVersion from
            # the fresh GET protect deletion/recreation and concurrent writers.
            await asyncio.to_thread(
                context.k8s_api.replace_namespaced_custom_object_status,
                **_GROUP, namespace=namespace, name=name, body=body,
                _request_timeout=(5, 10))
            return replacement
        except Exception as exc:
            code = getattr(exc, "status", None)
            if code == 404:
                return None
            if code == 409 and attempt < 4:
                await asyncio.sleep(0.05 * (attempt + 1))
                continue
            # A retry can publish a cached verdict, but must not repeat POST.
            raise kopf.TemporaryError(
                f"StatusWriteError: {type(exc).__name__}", delay=2) from None
    return None


def _terminal(running, result=None, error=None, duration=0.0):
    completed = _now()
    execution = _execution(running)
    status = dict(startTime=running["startTime"], completionTime=completed,
                  conditions=[execution] if execution else [])
    if error is not None:
        status.update(phase="Failed", result="error", message=error,
                      error=error, duration=duration, notifications=[])
        condition = dict(type="Failed", status="True", reason="ExecutionError", message=error)
    else:
        values = result.model_dump(mode="json")
        failed = values["status"] == "error"
        message = values["message"] or "RemoteExecutionError: execution failed"
        status.update(phase="Failed" if failed else "Completed", result=values["status"],
                      message=message, duration=values["duration"],
                      notifications=values.get("notifications") or [])
        for source, target in (("rationale", "rationale"), ("error", "error"),
                               ("model_used", "modelUsed")):
            if values.get(source) is not None:
                status[target] = values[source]
        if failed:
            status["error"] = values.get("error") or message
        reason = "ExecutionError" if failed else ("CheckPassed" if values["status"] == "pass" else "CheckFailed")
        condition = dict(type="Failed" if failed else "Complete", status="True",
                         reason=reason, message=message)
    condition["lastTransitionTime"] = completed
    status["conditions"].append(condition)
    return status


async def _publish(name, namespace, uid, started, terminal):
    def finish(resource):
        current = resource.get("status", {})
        if current.get("startTime") != started or current.get("phase") != "Running":
            return None  # Superseded rerun or already committed terminal write.
        return terminal
    await _status_change(name, namespace, uid, finish)
    _RESULTS.pop((uid, started), None)


async def _run(name, namespace, uid, request_id, rerun=False):
    began = time.monotonic()
    wall_started = time.time()
    started = _now()
    parsed = None

    def claim(resource):
        nonlocal parsed
        current = resource.get("status", {})
        owner = _execution(current)
        if owner and owner.get("message") == request_id:
            if (current.get("phase") == "Running"
                    and (uid, current.get("startTime")) not in _ACTIVE):
                # A claim PUT can commit even when its response is lost.
                # Retrying that handler closes uncertainty, never repeats POST.
                return _terminal(current, error="ExecutionInterrupted: execution ownership uncertain; POST not replayed")
            return None
        if not rerun and current.get("phase") in ("Running", "Completed", "Failed"):
            return None
        if rerun and resource.get("metadata", {}).get("annotations", {}).get("holmesgpt.dev/rerun") != "true":
            return None
        # Validate only after deciding this UID/request has not already run.
        # Invalid input still gets a single durable execution claim + failure.
        try:
            parsed = HealthCheckSpec(**resource.get("spec", {}))
        except Exception:
            parsed = None
        return dict(phase="Running", startTime=started, conditions=[dict(
            type="Execution", status="True", reason="ExecutionClaimed",
            message=request_id, lastTransitionTime=started)])

    # A previously computed result survives transient status write failures.
    for (cached_uid, cached_start), terminal in list(_RESULTS.items()):
        if cached_uid == uid:
            await _publish(name, namespace, uid, cached_start, terminal)
    running = await _status_change(name, namespace, uid, claim)
    if running is None or running.get("phase") != "Running":
        return
    key = (uid, started)
    _ACTIVE.add(key)
    try:
        if parsed is None:
            terminal = _terminal(running, error="ValidationError: invalid HealthCheck spec")
        else:
            try:
                result = await context.api_client.execute_check(
                    check_name=f"{namespace}/{name}", query=parsed.query,
                    timeout=parsed.timeout, mode=parsed.mode.value,
                    destinations=[d.model_dump() for d in parsed.destinations],
                    model=parsed.model, execution_id=f"{uid}/{started}",
                    deadline_unix=wall_started + parsed.timeout)
                terminal = _terminal(running, result=result)
            except asyncio.CancelledError:
                terminal = _terminal(running, error="ExecutionCancelled: outcome unknown; execution not replayed",
                                     duration=time.monotonic() - began)
                _RESULTS[key] = terminal
                await asyncio.shield(_publish(name, namespace, uid, started, terminal))
                raise
            except Exception as exc:
                # Only the local client's explicitly sanitized errors are safe
                # to retain verbatim; arbitrary exception bodies are not.
                error = (str(exc) if isinstance(exc, HolmesExecutionError)
                         else f"{type(exc).__name__}: execution failed; POST not replayed")
                terminal = _terminal(running, error=error,
                                     duration=time.monotonic() - began)
        _RESULTS[key] = terminal
        await _publish(name, namespace, uid, started, terminal)
    finally:
        _ACTIVE.discard(key)


@kopf.on.create("holmesgpt.dev", "v1alpha1", "healthchecks")
async def on_healthcheck_create(spec: Dict[str, Any], name: str, namespace: str,
                                uid: str, logger: kopf.Logger, **kwargs: Any):
    await _run(name, namespace, uid, f"create:{uid}")


@kopf.on.update("holmesgpt.dev", "v1alpha1", "healthchecks")
async def on_healthcheck_update(old: Dict[str, Any], new: Dict[str, Any], name: str,
                                namespace: str, logger: kopf.Logger, **kwargs):
    annotation = "holmesgpt.dev/rerun"
    metadata = new.get("metadata", {})
    if (metadata.get("annotations", {}).get(annotation) == "true"
            and old.get("metadata", {}).get("annotations", {}).get(annotation) != "true"):
        # Kopf's first-attempt timestamp is stable even when retry/status
        # writes change the resourceVersion before the handler is retried.
        first_attempt = kwargs.get("started")
        token = first_attempt.isoformat() if first_attempt is not None else metadata["resourceVersion"]
        await _run(name, namespace, metadata["uid"], f"rerun:{token}", rerun=True)


@kopf.on.resume("holmesgpt.dev", "v1alpha1", "healthchecks")
async def on_healthcheck_resume(name: str, namespace: str, uid: str, **kwargs):
    def recover(resource):
        current = resource.get("status", {})
        started = current.get("startTime")
        if current.get("phase") != "Running" or (uid, started) in _ACTIVE:
            return None
        cached = _RESULTS.get((uid, started))
        if cached is not None:
            return cached
        return _terminal(current, error="ExecutionInterrupted: outcome unknown after operator restart; POST not replayed")
    await _status_change(name, namespace, uid, recover)
