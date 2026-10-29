# SPDX-FileCopyrightText: HolmesGPT contributors
# SPDX-License-Identifier: Apache-2.0
"""Replacement for HolmesGPT 0.45.0 holmes/checks/checks_api.py.

The API owns one budget from entry through fresh-process initialization,
collection/investigation, compaction, verdict, usage recording and notification.
"""

import asyncio
import time
from typing import Optional

from fastapi import FastAPI, Request
from pydantic import BaseModel, Field

from holmes.checks.models import CheckMode, CheckStatus
from holmes.checks.home_ops_check_runtime import error_result, run_worker
from holmes.config import Config

checks_app = FastAPI()
_CONFIG: Config


def init_checks_app(main_app: FastAPI, config: Config):
    global _CONFIG
    _CONFIG = config
    main_app.mount("/api/checks", checks_app)


class CheckExecutionRequest(BaseModel):
    query: str
    name: Optional[str] = None
    timeout: int = Field(default=30, ge=1)
    mode: CheckMode = CheckMode.MONITOR
    destinations: list[dict] = Field(default_factory=list)
    model: Optional[str] = None
    execution_id: Optional[str] = None
    deadline_unix: Optional[float] = Field(default=None, allow_inf_nan=False)


class NotificationStatus(BaseModel):
    type: str
    channel: Optional[str] = None
    status: str
    error: Optional[str] = None


class CheckExecutionResponse(BaseModel):
    status: CheckStatus
    message: str
    duration: float
    rationale: Optional[str] = None
    error: Optional[str] = None
    model_used: Optional[str] = None
    notifications: Optional[list[NotificationStatus]] = None


@checks_app.post("/execute")
async def execute_health_check(request: CheckExecutionRequest,
                               http_request: Request) -> CheckExecutionResponse:
    started = time.monotonic()
    remaining = float(request.timeout)
    if request.deadline_unix is not None:
        remaining = min(remaining, request.deadline_unix - time.time())
    deadline = started + max(0.0, remaining)
    # This is the same source used by server.init_config in the pinned image.
    # Reconstruct inside exec, never pickle live clients, locks or thread pools.
    source = getattr(_CONFIG, "_config_file_path", None)
    payload = {"request": request.model_dump(mode="json"),
               "config_file": str(source) if source is not None else None,
               "deadline": deadline}
    try:
        result = await run_worker(payload, deadline, http_request.is_disconnected)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        result = error_result(type(exc).__name__)
    result["duration"] = time.monotonic() - started
    return CheckExecutionResponse(**result)
