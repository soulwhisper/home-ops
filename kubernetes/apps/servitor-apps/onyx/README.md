# Onyx

Enterprise search/RAG (helm chart `onyx@0.8.23`, images `onyxdotapp/onyx-*:v4.7.2`).

## Upgrade postmortem (2026-09-14, v4.7.1 → v4.7.2)

HelmRelease stalled after 4 failed attempts, rolled back to v14:

- `onyx-model-server` is a multi-GB image (models baked in, see
  `temp_huggingface` in the startup logs). Pulling it through the flapping
  tproxy never finished inside helm's 5m default window → pre-pull images on
  all nodes before big upgrades: `talosctl -n <node> image pull --namespace cri <img>`
- Chart ships **zero probes** for `inferenceCapability` / `indexCapability`;
  torch init throttled at the 2-CPU limit takes **~10min** before the server
  answers. Fixed with `startupProbe` + `spec.timeout: 20m` in
  `app/helmrelease.yaml`.
- Health path is **`/api/health`**, not `/health` (404) — verify via the model
  server's own `/openapi.json` when in doubt. Model containers are distroless
  (no `sh`, no `wget`); probe via a curl pod against the ClusterIP service.

## Switching embeddings/rerank to agentgateway (macstudio / siliconflow)

Verified against onyx source @ main (`backend/onyx`): the `litellm` provider
types are generic self-hosted endpoints, exact match for our gateway.

| Provider | Onyx behavior | Our endpoint |
|---|---|---|
| `EmbeddingProvider.LITELLM` | POST `{api_url}` `{model, input}` Bearer → `data[].embedding` (search_nlp_models.py:555) | `…/v1/embeddings` or `/sf/embeddings` |
| `RerankerProvider.LITELLM` | POST `{api_url}` `{model, query, documents}` → `results[index, relevance_score]` (:750) | `…/v1/rerank` or `/sf/rerank` |

API providers bypass the model servers entirely ("API providers don't need
model server endpoint", :1240) — they go idle (the resourcing doc's
"significantly less memory" case) but **must stay deployed**; onyx has no
no-model-server mode.

Config is **DB-driven via admin REST** (not helm values):

1. Smoke-test (needs `FULL_ADMIN_PANEL_ACCESS` session or PAT):
   `POST /admin/embedding/test-embedding`
   `{provider_type: "litellm", api_url: "http://agentgateway-proxy.networking-system.svc.cluster.local:80/sf/embeddings", model_name: "Qwen/Qwen3-Embedding-4B", api_key: "<gateway key>"}`
2. Register provider: `PUT /admin/embedding/provider` (same fields).
3. Switch: `POST /search-settings/set-new-search-settings` with
   `model_name: "Qwen/Qwen3-Embedding-4B"`, `provider_type: "litellm"`,
   `model_dim: 2560`, `switchover_type: "REINDEX"`.
4. Reranker: admin UI → Search Settings → Reranking → `litellm` with
   `api_url: …/sf/rerank` (prod `/docs` disabled; confirm exact API live).
5. After the swap completes, shrink model-server resources in values.

Cautions: full corpus **re-index** (old model serves during the swap; hours at
the default 2-CPU indexing limit — raise `indexCapability` limits for the
window on large corpora). Embeddings traffic becomes gateway-dependent;
studio↔SF lanes share the same 2560d space, so either lane is safe.

## Suitability eval: all model serving out-of-cluster

**Onyx stays suitable.** The `litellm` path makes model location irrelevant;
its differentiators (50+ connectors, hybrid search with permissioning,
background re-index swap) have no equal-weight substitute. Costs: two idle
model-server shells (~250m CPU request each), DB-driven (non-GitOps) provider
config, one-time re-index.

Alternatives only win if "zero model pods" is a hard requirement:

| Option | External embeddings/rerank | Tradeoff |
|---|---|---|
| **Open WebUI** | ✅ native (`RAG_EMBEDDING_ENGINE=openai` + custom base URL; external rerank) | lightest ops (1 pod); connectors = web/Drive only, weaker permissioning |
| **AnythingLLM** | ✅ custom OpenAI-compatible | workspace model; small connector set |
| **Dify** | ✅ provider plugins (OpenAI-compatible embeddings + custom rerank) | heavier platform (api/worker/web/plugin-daemon + vector DB); previously ran here, archived |
| **RAGFlow** | ✅ custom endpoints | deepest doc parsing; heavyweight (ES+MySQL+Redis+MinIO) |
| kotaemon / MaxKB | ✅ litellm-style providers | smaller ecosystem, CN-friendly |

Decision: keep onyx; flip providers per the runbook above. Revisit Open WebUI
only if the need narrows to "chat over documents" without connector breadth.
