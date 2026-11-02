# SPDX-License-Identifier: Apache-2.0
"""Fixed, non-sensitive health-check execution failure classes."""

EXECUTION_FAILURES = (
    ("Failed to parse response:", "verdict parsing failed"),
    ("Check produced no successful tool output", "no successful tool output"),
    ("Verdict rejected:", "verdict rejected by evidence gate"),
)
EXECUTION_FAILURE_PREFIXES = tuple(prefix for prefix, _ in EXECUTION_FAILURES)
