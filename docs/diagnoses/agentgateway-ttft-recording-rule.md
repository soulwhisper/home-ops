# Agentgateway TTFT recording rule: diagnosis

**Status:** no recent TTFT observations in the sampled window; verify streaming
emission before changing the recording rule.
**Original diagnosis:** 2026-11-12 · **Last evidence check:** 2026-11-21
**Scope:** `agentgateway:gen_ai_ttft:p95_5m` in the `agentgateway.rules` group of
`kubernetes/apps/monitoring-system/victoria-metrics/cluster/prometheusrule.yaml`.

## Signal

`RecordingRulesNoData` (severity `info`) has been continuously active for this
recording rule since `2026-11-10T14:33:30Z`. The alert is emitted by vmalert, not
by a repo rule: it means the recording rule produced no samples in the
evaluation window.

## Evidence

All queries run against VMSingle at `2026-11-12T03:01:35Z`. Range-query rows
name their lookback; instant rows are as of that capture time.

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
(for example 28 and 28 on one persona-route series). The values are simply
frozen.

At `2026-11-21T01:19:24Z`, vmalert still returned zero TTFT samples.
During the previous seven days the TTFT `_count` increased by `0`, although
the gateway request counter increased by `2677`. Both proxy scrape targets
were up. A successful chat-completion trace showed end-to-end latency, not
that a streaming client received a first token. A separate authenticated,
read-only MCP exercise restored samples to the MCP recording; that does not
test TTFT.

## Mechanism

In Agentgateway v1.7.0,
[`LLMContext::set_token_timing`](https://github.com/agentgateway/agentgateway/blob/v1.7.0/crates/agentgateway/src/cel/types.rs#L1796-L1803)
computes `time_to_first_token` from the gateway-captured `first_token`
timestamp and request start. The [histogram writer](https://github.com/agentgateway/agentgateway/blob/v1.7.0/crates/agentgateway/src/telemetry/log.rs#L1020-L1028)
records that duration if present; it is not a field supplied by the upstream
response. The production evidence does not show whether a client streamed
output or the gateway captured a first token. With no new observations, an
all-zero bucket rate yields no TTFT result in VMSingle. An empty recording
alone does not prove a malformed rule or a failed scrape.

No gateway configuration disables streaming: `httproute.yaml` only raises the
timeout so long streams are not cut. Streaming is therefore client-decided.

## Next check and acceptance

Use an existing verified streamed completion on a specific lane or one approved
streaming probe. Record the request window, route, model, and confirmation that
the client received streamed output. Compare the route/model `_count` before
and after using `increase(agentgateway_gen_ai_server_time_to_first_token_count[5m])`
and check the matching `+Inf` bucket and `agentgateway:gen_ai_ttft:p95_5m`.

- `_count` advances and the recording produces a sample: the measurement path
  works. If observations are too sparse for the 5-minute use case, separately
  review an explicitly renamed longer window.
- `_count` advances but the recording stays empty: compare the raw bucket
  representation and labels with the expression before changing it.
- Verified streamed output but `_count` does not advance: check whether the
  gateway captured `first_token` on that response path and finalized the
  duration. If the trace carries `agw.ai.time_to_first_token` but the counter
  still does not advance, check histogram emission and scraping. Do not
  suppress the absence alert.
- No verified streaming observation: leave the rule and alert enabled; the
  cause remains unverified.
