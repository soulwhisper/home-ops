# Agentgateway TTFT recording rule: diagnosis

**Status:** open, awaiting a longer watch and a decision. Nothing is changed by this page.
**Date:** 2026-11-12
**Scope:** `agentgateway:gen_ai_ttft:p95_5m` in the `agentgateway.rules` group of
`kubernetes/apps/monitoring-system/victoria-metrics/cluster/prometheusrule.yaml`.

## Signal

`RecordingRulesNoData` (severity `info`) has been continuously active for this
recording rule since `2026-11-10T14:33:30Z`. The alert is emitted by vmalert, not
by a repo rule: it means the recording rule produced no samples in the
evaluation window.

## Evidence

All queries run against VMSingle at `2026-11-12T03:01:35Z`; each row names its
own lookback.

| Query | Result |
| --- | --- |
| `count(agentgateway:gen_ai_ttft:p95_5m)` | empty — no recorded series |
| `count_over_time(agentgateway:gen_ai_ttft:p95_5m[7d])` | empty; the 7d lookback spans the rule's whole life (added `2026-11-10`) |
| `count(agentgateway_gen_ai_server_time_to_first_token_bucket)` | 102 series |
| `count(count by (le) (agentgateway_gen_ai_server_time_to_first_token_bucket))` | 17 distinct `le` values |
| `sum(rate(agentgateway_gen_ai_server_time_to_first_token_bucket{le="+Inf"}[5m]))` | 0 |
| `max(changes(agentgateway_gen_ai_server_time_to_first_token_count[24h]))` | 0 — no new observations in 24h |
| `max(changes(agentgateway_gen_ai_client_token_usage_count[24h]))` | 27 — the busiest GenAI series does advance |
| `sum(changes(agentgateway_requests_total[24h]))` | 1980 |
| `up{job="networking-system/agentgateway-proxy"}` | 1 |
| `time() - max(timestamp(agentgateway_gen_ai_server_time_to_first_token_bucket))` | 0.22 s — scrape path is healthy |

The histogram itself is internally consistent: for a given
`gen_ai_request_model` + `route` series the `+Inf` bucket equals `_count`
(for example 28 and 28 on the persona route). The values are simply frozen.

## Mechanism

The TTFT histogram is believed to be observed only for streamed completions;
whether the upstream records anything for a non-streaming response is
unverified (see Open questions). With no observations, every bucket rate over
5m is `0`, and `histogram_quantile` over all-zero buckets evaluates to an
empty vector in VMSingle, so the recording rule writes nothing. The rule is
structurally idle, not broken.

The AI workload is not persistent: chats arrive in sessions rather than as
steady load. The same 24h window carries 27 changes on the busiest token-usage
series and zero TTFT observations, so one quiet day cannot distinguish "no
streaming client" from "no traffic at all". That is why this page records
evidence instead of removing the rule.

No gateway configuration disables streaming: `httproute.yaml` only raises the
timeout so long streams are not cut. Streaming is therefore client-decided.

## Options

| Option | Change | Trade-off |
| --- | --- | --- |
| A. Remove the rule | Delete `agentgateway:gen_ai_ttft:p95_5m` and the sentence advertising it in `docs/application/monitoring.md` | Matches the existing precedent: synced rule groups that are empty by design are disabled rather than tolerated (`helmrelease.yaml`, `RecordingRulesNoData` comment). Loses the series if streaming is adopted later. |
| B. Widen the window | Evaluate over `[1h]` or `[6h]` instead of `[5m]`, and rename the recording and its documentation to the new window | A sparse signal would then produce a value, but a six-hour p95 is a different measurement and will look stale next to the other 5m recordings; keeping the `_5m` name would mislabel it. |
| C. Make streaming the reported path | Client/gateway change so the lanes that should report TTFT stream | Fixes the root cause, but is a product decision and cannot be validated from the metrics alone. |
| D. Scope the alert | Restrict `RecordingRulesNoData` to rules expected to be dense | Broadest blast radius; this alert has already caught real gaps and should not be weakened to accommodate one idle rule. |

## Recommendation

Decide on a longer window than one day. Record 7–14 days of
`sum(changes(agentgateway_gen_ai_server_time_to_first_token_count[24h]))`
alongside token-usage changes, and send at least one known-streaming request
in that window. Only a streaming request observed with a zero change count
proves the rule idle rather than merely quiet.

If no streaming client exists and none is planned, take A. If TTFT is wanted,
take C first and then B, validating with the same streaming request before
changing the rule.

## Verification

- Observation: the 7–14 day watch above; treat a single quiet day as
  inconclusive.
- A: `count(agentgateway:gen_ai_ttft:p95_5m)` stays empty by design and
  `ALERTS{alertname="RecordingRulesNoData", recording="agentgateway:gen_ai_ttft:p95_5m"}`
  clears within one evaluation interval.
- B: the recording produces a sample only after a streaming request; confirm
  with a known-streaming call rather than waiting for traffic.
- C: `sum(changes(agentgateway_gen_ai_server_time_to_first_token_count[1h])) > 0`
  after the first streaming request.

## Open questions

- Is any client on the Studio lanes using `stream=true` today? Unverified.
- Does the upstream emit TTFT for non-streaming completions? Assumed no.
