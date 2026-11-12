# Agentgateway TTFT recording rule: diagnosis

**Status:** open, awaiting a decision. Nothing is changed by this page.
**Date:** 2026-11-12
**Scope:** `agentgateway:gen_ai_ttft:p95_5m` in the `agentgateway.rules` group of
`kubernetes/apps/monitoring-system/victoria-metrics/cluster/prometheusrule.yaml`.

## Signal

`RecordingRulesNoData` (severity `info`) has been continuously active for this
recording rule since `2026-11-10T14:33:30Z`. The alert is emitted by vmalert, not
by a repo rule: it means the recording rule produced no samples in the
evaluation window.

## Evidence

All queries run against VMSingle at `2026-11-12T01:5xZ`, 24h lookback.

| Query | Result |
| --- | --- |
| `count(agentgateway:gen_ai_ttft:p95_5m)` | 0 series |
| `count_over_time(agentgateway:gen_ai_ttft:p95_5m[24h])` | 0 — the rule has never produced a sample |
| `count(agentgateway_gen_ai_server_time_to_first_token_bucket)` | 102 series over 17 `le` values |
| `sum(rate(agentgateway_gen_ai_server_time_to_first_token_bucket{le="+Inf"}[5m]))` | 0 |
| `sum(changes(agentgateway_gen_ai_server_time_to_first_token_count[24h]))` | 0 — no new observations in 24h |
| `sum(changes(agentgateway_gen_ai_client_token_usage_count[24h]))` | 27 on the busiest series — GenAI metrics do advance |
| `sum(changes(agentgateway_requests_total[24h]))` | 1984 |
| `up{job="networking-system/agentgateway-proxy"}` | 1, samples ~5s old |
| `timestamp` age of the TTFT series | ~5s — scrape path is healthy |

The histogram itself is internally consistent: for a given
`gen_ai_request_model` + `route` series the `+Inf` bucket equals `_count`
(for example 28 and 28 on the persona route). The values are simply frozen.

## Mechanism

`agentgateway_gen_ai_server_time_to_first_token_*` is only observed when a
completion is streamed; the gateway has no observation to record for a
non-streaming response. Current traffic produces token-usage and request
counters but no TTFT observations, so every bucket rate over 5m is `0`.
`histogram_quantile` over all-zero buckets yields `NaN`, and the recording
rule therefore writes nothing. The rule is structurally idle, not broken.

No gateway configuration disables streaming: `httproute.yaml` only raises the
timeout so long streams are not cut. Streaming is therefore client-decided.

## Options

| Option | Change | Trade-off |
| --- | --- | --- |
| A. Remove the rule | Delete `agentgateway:gen_ai_ttft:p95_5m` and the sentence advertising it in `docs/application/monitoring.md` | Matches the existing precedent: synced rule groups that are empty by design are disabled rather than tolerated (`helmrelease.yaml`, `RecordingRulesNoData` comment). Loses the series if streaming is adopted later. |
| B. Widen the window | Evaluate over `[1h]` or `[6h]` instead of `[5m]` | A sparse signal would then produce a value, but a six-hour p95 is a different measurement and will look stale next to the other 5m recordings. |
| C. Make streaming the reported path | Client/gateway change so the lanes that should report TTFT stream | Fixes the root cause, but is a product decision and cannot be validated from the metrics alone. |
| D. Scope the alert | Restrict `RecordingRulesNoData` to rules expected to be dense | Broadest blast radius; this alert has already caught real gaps and should not be weakened to accommodate one idle rule. |

## Recommendation

Decide whether TTFT is a signal we intend to act on. If not, take A. If it is,
take C first and then B, and validate with a real streaming request before
changing the rule.

## Verification

- A: `count(agentgateway:gen_ai_ttft:p95_5m)` stays 0 by design and
  `ALERTS{alertname="RecordingRulesNoData", recording="agentgateway:gen_ai_ttft:p95_5m"}`
  clears within one evaluation interval.
- B: the recording produces a sample only after a streaming request; confirm
  with a known-streaming call rather than waiting for traffic.
- C: `sum(changes(agentgateway_gen_ai_server_time_to_first_token_count[1h])) > 0`
  after the first streaming request.

## Open questions

- Is any client on the Studio lanes using `stream=true` today? Unverified.
- Does the upstream emit TTFT for non-streaming completions? Assumed no.
