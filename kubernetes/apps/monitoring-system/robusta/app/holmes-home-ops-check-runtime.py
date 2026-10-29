# SPDX-License-Identifier: Apache-2.0
"""Linux exec-worker containment for the complete health-check budget."""

import asyncio
import ctypes
import json
import os
import signal
import sys
import time

CLEANUP_GRACE = 0.75


def error_result(kind, duration=0.0):
    message = f"{kind}: health check execution did not complete"
    return dict(status="error", message=message, rationale=message, error=message,
                duration=duration, model_used=None, notifications=[])


def _adopt_descendants():
    # Workers can launch shell/tool grandchildren. Adopt and reap them rather
    # than relying on the container's PID 1 to collect killed orphan processes.
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        raise OSError(ctypes.get_errno(), "Cannot contain check descendants")


def _signal_group(pid, sig):
    try:
        os.killpg(pid, sig)
    except ProcessLookupError:
        pass


async def _stop_group(process):
    _signal_group(process.pid, signal.SIGTERM)
    # Give HTTP clients a chance to close their sockets before SIGKILL. The
    # grace is cleanup-only; a result arriving here cannot become a verdict.
    await asyncio.sleep(CLEANUP_GRACE)
    _signal_group(process.pid, signal.SIGKILL)
    await process.wait()
    until = time.monotonic() + CLEANUP_GRACE
    while True:
        try:
            pid, _ = os.waitpid(-process.pid, os.WNOHANG)
        except ChildProcessError:
            return
        if pid == 0:
            if time.monotonic() >= until:
                return
            await asyncio.sleep(0.01)


async def run_worker(payload, deadline, disconnected=None, command=None):
    """Run one fresh interpreter; deadline is absolute CLOCK_MONOTONIC.

    Request/configuration data travels on stdin, never argv or a shared file.
    stdout/stderr are discarded; a dedicated inherited pipe carries JSON only.
    ``command`` is an internal test seam, never an HTTP request field.
    """
    started = time.monotonic()
    if started >= deadline:
        return error_result("DeadlineExceeded")
    _adopt_descendants()
    read_fd, write_fd = os.pipe()
    process = None
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    transport = None
    io_task = watch_task = None
    try:
        transport, _ = await asyncio.get_running_loop().connect_read_pipe(
            lambda: protocol, os.fdopen(read_fd, "rb", buffering=0))
        read_fd = None
        env = dict(os.environ, HOME_OPS_CHECK_RESULT_FD=str(write_fd))
        spawn = asyncio.create_task(asyncio.create_subprocess_exec(
            *(command or [sys.executable, "-m", "holmes.checks.home_ops_check_worker"]),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL, start_new_session=True,
            pass_fds=(write_fd,), env=env))
        try:
            process = await asyncio.shield(spawn)
        except asyncio.CancelledError:
            # Cancellation can land after exec but before subprocess creation
            # returns. Retrieve ownership before entering the cleanup path.
            process = await spawn
            raise
        os.close(write_fd)
        write_fd = None

        async def exchange():
            process.stdin.write(json.dumps(payload).encode())
            await process.stdin.drain()
            process.stdin.close()
            data = await reader.read()
            await process.wait()
            if process.returncode != 0:
                return error_result("WorkerExit")
            return json.loads(data)

        async def watch_disconnect():
            while True:
                if disconnected is not None and await disconnected():
                    return
                await asyncio.sleep(0.05)

        io_task = asyncio.create_task(exchange())
        watch_task = asyncio.create_task(watch_disconnect())
        done, _ = await asyncio.wait(
            (io_task, watch_task), timeout=max(0, deadline - time.monotonic()),
            return_when=asyncio.FIRST_COMPLETED)
        if watch_task in done:
            raise asyncio.CancelledError("Health check client disconnected")
        if io_task not in done or time.monotonic() >= deadline:
            result = error_result("DeadlineExceeded")
        else:
            result = io_task.result()
        result["duration"] = time.monotonic() - started
        return result
    finally:
        for task in (io_task, watch_task):
            if task is not None:
                task.cancel()
        if process is not None:
            cleanup = asyncio.create_task(_stop_group(process))
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                await cleanup
                raise
        for task in (io_task, watch_task):
            if task is not None:
                await asyncio.gather(task, return_exceptions=True)
        if transport is not None:
            transport.close()
        for fd in (read_fd, write_fd):
            if fd is not None:
                os.close(fd)
