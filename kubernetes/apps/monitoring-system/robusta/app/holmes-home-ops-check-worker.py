# SPDX-FileCopyrightText: HolmesGPT contributors
# SPDX-License-Identifier: Apache-2.0
"""Fresh exec entrypoint for the HolmesGPT 0.45.0 check API replacement."""

import json
import os
import signal
import sys
import time
from pathlib import Path


def _notify(request, result, config):
    # Preserve the pinned API's supported Slack destination and notification
    # shape. Delivery is part of the same worker budget, not a detached task.
    if result["status"] != "fail" or request["mode"] != "alert":
        return []
    from holmes.core.issue import Issue, IssueStatus
    from holmes.core.tool_calling_llm import LLMResult
    from holmes.plugins.destinations.slack.plugin import SlackDestination

    name = request.get("name") or "api-check"
    issue = Issue(
        id=f"healthcheck-{name}-{int(time.time())}", name=f"Health Check Failed: {name}",
        source_instance_id=config.cluster_name or "unknown", source_type="HealthCheck",
        presentation_status=IssueStatus.OPEN,
        presentation_key_metadata=f"*Check:* `{name}`\n*Query:* {request['query']}",
        show_status_in_title=False)
    llm_result = LLMResult(result=result.get("rationale") or result["message"],
                           tool_calls=[], messages=[])
    notifications = []
    for destination in request.get("destinations", []):
        if destination.get("type", "").lower() != "slack":
            continue
        options = destination.get("config", {})
        token = options.get("token") or os.environ.get("SLACK_TOKEN")
        channel = options.get("channel") or os.environ.get("SLACK_CHANNEL")
        notification = dict(type="slack", status="skipped")
        if not token or not channel:
            notification["error"] = "SLACK_TOKEN or SLACK_CHANNEL not configured"
        else:
            notification["channel"] = channel
            try:
                SlackDestination(token=token, channel=channel).send_issue(issue, llm_result)
                notification["status"] = "sent"
            except Exception as exc:
                notification.update(status="failed", error=f"{type(exc).__name__}: notification delivery failed")
        notifications.append(notification)
    return notifications


def execute(payload):
    request = payload["request"]
    from holmes.checks.home_ops_collectors import collect

    result = collect(request["query"], payload["deadline"])
    if result is not None and (result["status"] != "fail" or request["mode"] != "alert"
                               or not request.get("destinations")):
        return result

    # Exact upstream server initialization sources: the actual Config path
    # (including relative tool/skill resolution) or the complete env loader.
    # Model lists/provider settings are loaded by the normal registry and DAL.
    from holmes.config import Config
    config_path = payload.get("config_file")
    if config_path is not None and not Path(config_path).is_file():
        raise FileNotFoundError("Health check configuration source is unavailable")
    config = (Config.load_from_file(Path(config_path)) if config_path is not None
              else Config.load_from_env())
    # Only this isolated HealthCheck config is bounded; interactive RCA keeps
    # the server's independently configured tool-step allowance.
    config.max_steps = min(config.max_steps, 12)
    if result is None:
        from holmes.checks.checks import execute_check
        from holmes.checks.models import Check, CheckMode
        from holmes.core.tools import SERVER_TOOLSET_TAGS, PrerequisiteCacheMode
        from holmes.core.usage_recorder import UsageRecorderState, resolve_provider

        ai = config.create_toolcalling_llm(
            dal=config.dal, toolset_tag_filter=SERVER_TOOLSET_TAGS,
            enable_all_toolsets_possible=False,
            prerequisite_cache=PrerequisiteCacheMode.DISABLED,
            reuse_executor=True, model=request.get("model"))
        model = getattr(ai.llm, "model", None) or request.get("model") or "unknown"
        check = Check(name=request.get("name") or "api-check", query=request["query"],
                      timeout=request["timeout"], mode=CheckMode(request["mode"]),
                      destinations=[d["type"] for d in request.get("destinations", [])
                                    if d.get("type")])
        recorder = UsageRecorderState(
            dal=config.dal, request_type="health_check", request_source="operator",
            source_ref=check.name, conversation_id=None, conversation_source=None,
            user_id=None, is_streaming=False, model=model, provider=resolve_provider(model),
            is_robusta_model=ai.llm.is_robusta_model,
            meta={"check_mode": request["mode"], "timeout": request["timeout"]})
        checked = execute_check(check=check, ai=ai, verbose=False,
                                console=None, recorder_state=recorder)
        result = dict(status=checked.status.value, message=checked.message,
                      rationale=checked.rationale, error=checked.error,
                      model_used=ai.llm.model)
        if result["status"] == "error":
            # Provider exceptions may embed credentials or full request data.
            result.update(message="CheckExecutionError: investigation failed",
                          error="CheckExecutionError: investigation failed")
        # Flush the existing recorder before worker exit. This wait also falls
        # within the parent's absolute budget, including any blocked DAL write.
        from holmes.core.usage_recorder import _RECORDER_EXECUTOR
        _RECORDER_EXECUTOR.shutdown(wait=True)
    result["notifications"] = _notify(request, result, config)
    return result


def main():
    # SIGTERM unwinds Python contexts to close downstream sockets; the parent
    # escalates to SIGKILL if any client/tool ignores that opportunity.
    def terminate(signum, frame):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, terminate)
    payload = json.load(sys.stdin)
    try:
        result = execute(payload)
    except Exception as exc:
        kind = type(exc).__name__
        message = f"{kind}: health check execution failed"
        result = dict(status="error", message=message, rationale=message,
                      error=message, model_used=None, notifications=[])
    fd = int(os.environ["HOME_OPS_CHECK_RESULT_FD"])
    with os.fdopen(fd, "w") as stream:
        json.dump(result, stream)


if __name__ == "__main__":
    main()
