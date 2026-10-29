# SPDX-FileCopyrightText: HolmesGPT contributors
# SPDX-License-Identifier: Apache-2.0
"""Replacement for HolmesGPT 0.45.0 holmes_operator/client/holmes_api_client.py."""

import asyncio
import time
from typing import Optional

import httpx

from holmes_operator.models import CheckResponse

# Covers server group termination/reaping and the final HTTP response only.
# Investigation never receives this grace as additional execution time.
RESPONSE_GRACE = 3.0


class HolmesExecutionError(RuntimeError):
    """Safe, nonempty error for an execution whose POST must not be replayed."""


class HolmesAPIClient:
    def __init__(self, base_url: str, timeout: int = 300):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout=timeout, connect=10.0),
            transport=httpx.AsyncHTTPTransport(
                retries=0, limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)))

    async def execute_check(self, check_name: str, query: str, timeout: int,
                            mode: str, destinations: list,
                            model: Optional[str] = None,
                            execution_id: Optional[str] = None,
                            deadline_unix: Optional[float] = None) -> CheckResponse:
        # Establish once, before connection acquisition or request transmission.
        # Wall time is for cross-pod transport; the API converts it once to its
        # local monotonic clock. asyncio.timeout bounds the whole HTTP exchange,
        # unlike httpx's per-read timeout (which resets on each received chunk).
        if deadline_unix is None:
            deadline_unix = time.time() + timeout
        remaining = min(float(timeout), deadline_unix - time.time())
        if remaining <= 0:
            raise HolmesExecutionError("DeadlineExceeded: execution budget expired before POST")
        payload = dict(name=check_name, query=query, timeout=timeout, mode=mode,
                       destinations=destinations, deadline_unix=deadline_unix)
        if model is not None:
            payload["model"] = model
        if execution_id is not None:
            payload["execution_id"] = execution_id
        budget = remaining + RESPONSE_GRACE
        try:
            async with asyncio.timeout(budget):
                response = await self.client.post(
                    f"{self.base_url}/api/checks/execute", json=payload,
                    timeout=httpx.Timeout(budget, connect=min(10.0, remaining)))
                response.raise_for_status()
                result = CheckResponse(**response.json())
                if result.status.value == "error" and not result.error:
                    result.error = "RemoteExecutionError: API execution failed"
                if not result.message:
                    result.message = result.error or "RemoteExecutionError: empty API response message"
                return result
        except httpx.HTTPStatusError as exc:
            raise HolmesExecutionError(
                f"HTTPStatusError: Holmes API returned HTTP {exc.response.status_code}; execution not replayed") from None
        except (httpx.RequestError, TimeoutError) as exc:
            raise HolmesExecutionError(
                f"{type(exc).__name__}: execution outcome unknown; POST not replayed") from None
        except (ValueError, TypeError, KeyError):
            raise HolmesExecutionError("InvalidResponse: Holmes API response could not be decoded; POST not replayed") from None

    async def close(self):
        await self.client.aclose()
