# AI Infrastructure Summary
Last updated: 2026-11-02

Source: Flux manifests in `kubernetes/apps/`.

## Architecture Overview

```mermaid
flowchart TB
    subgraph Clients["AI Clients"]
        Hermes["Hermes Agent"]
        Tavern["DSH Tavern"]
        DSHW["dsh-web (cluster)"]
        OWUI["Open WebUI"]
        HS["Hindsight"]
    end

    subgraph Gateway["Agent Gateway"]
        AG-LLM["LLM Routing<br/>header-based: x-model"]
        AG-MCP["MCP Routing<br/>7 VirtualMCP tiers"]
    end

    subgraph LLM["LLM Providers"]
        Studio["MacStudio oMLX<br/>Qwen3.8-27B + Ornith-1.5-35B + MiniCPM-o 4.5<br/>(MLX 4bit, 10.10.0.210)"]
        External["DeepSeek API"]
    end

    subgraph MCP["MCP Gateway (ToolHive)"]
        VMCP-SEARCH["search<br/>(3 servers: web/news/docs)"]
        VMCP-CLUSTER["cluster<br/>(6 servers: monitoring/k8s)"]
        VMCP-GITHUBRO["github-ro<br/>(1 server: read-only code)"]
        VMCP-HOME["persona<br/>(2 servers: smart home/persona)"]
        VMCP-AGENT["agent<br/>(2 servers: forgejo + incident memory)"]
        VMCP-BROWSER["browser<br/>(1 server: Playwright)"]
        VMCP-GITHUBPR["github-pr<br/>(1 server: branch/commit/PR)"]
    end

    subgraph Obs["Observability"]
        Langfuse["Langfuse"]
    end

    Clients --> AG-LLM
    Clients --> AG-MCP
    AG-LLM --> Studio
    AG-MCP --> VMCP-SEARCH
    AG-MCP --> VMCP-CLUSTER
    AG-MCP --> VMCP-GITHUBRO
    AG-MCP --> VMCP-HOME
    AG-MCP --> VMCP-AGENT
    AG-MCP --> VMCP-BROWSER
    AG-MCP --> VMCP-GITHUBPR
    Tavern --> External
    DSHW --> External
    Clients --> Obs
```

## Agent Gateway — Central LLM + MCP Router

The agent gateway is the single entry point for all agentgateway-managed LLM lanes and MCP traffic. UI-configured external providers (DeepSeek) connect directly from DSH apps; Hermes always uses the gateway for LLM and MCP calls.

### LLM lanes

Each model has an independent HTTPRoute and authentication policy. Chat inference
shares `POST /v1/chat/completions`; model discovery is
`GET /v1/models/<model>` on the same route and uses the same credential. The
guarded/open split is a **model name** (body `model` → `x-model` header via
the gateway-wide PreRouting transform); guardrails attach to the guarded chat
rules by section name:

| Client model | promptGuard | Backend | Model (studio id) |
| ------------ | ----------- | ------- | ----------------- |
| `uncensored` | none (open lane) | `llm-backend-uncensored` | Qwen3.8-27B Uncensored (`qwen3.8-27b`, MLX 4bit) — pure chat only |
| `persona` | none (open lane) | `llm-backend-persona` | Orion-26B-A4B-v1.1 (`orion-1.1-26b-a4b`, MLX 4bit) — RP/identity-bound chat |
| `agent` | **guarded** | `llm-backend-agent` | Ornith-1.5-35B (`ornith-1.5-35b-a3b`, MLX 4bit) — AI-ops automation |
| `omni` | **guarded** | `llm-backend-omni` | MiniCPM-O-4.5 (`minicpm-o-4.5`, text+vision+audio-in) |

Consumer base URLs
are `.../v1` — OpenAI/litellm clients append `/chat/completions`
themselves; raw-HTTP consumers must use the full path.

There is no catch-all: an unknown or missing model id matches no rule and
the gateway answers `404`. `uncensored` and `persona` are the unguarded
lanes — open chat and identity-bound RP respectively. `omni` is reachable
exclusively guarded. All backends
speak the OpenAI-compatible API on `studio.homelab.internal:8000` and
inject the oMLX server key via `policies.auth.secretRef`
(`studio-api-auth`). Consumers authenticate with **per-lane** API keys
(ExternalSecret-managed from the 1Password `agentgateway` item; format
`llm-<lane>-<hex16>`): `llm_uncensored` (open chat / open-webui),
`llm_persona` (dsh-tavern RP), `llm_agent` (hermes, robusta), `llm_omni`
(extractors, hermes aux). Each model route carries its own
apiKeyAuthentication policy covering both inference and discovery, so a chat
key cannot call the automation lane. Each route accepts only its own lane key;
a consumer that needs a second lane holds that lane's key directly — hermes
keeps `llm_agent` for its main brain and `llm_omni` as `OPENAI_AUX_API_KEY`
for auxiliary tasks. open-webui uses only `llm_uncensored` for chat and has no
omni credential. Each media model has its own route, credential, and field in
the `agentgateway` 1Password item:
`llm-embedding-auth` uses `llm_embedding`, `llm-reranker-auth` uses
`llm_reranker`, and `llm-audio-auth` uses `llm_audio`. Chat-lane keys do not
implicitly authorize media inference or discovery.

**Key rotation/revocation:** update the value in the 1Password `agentgateway`
item, force the owning ExternalSecret to reconcile
(`kubectl annotate externalsecret -n <namespace> <name> force-sync="$(date +%s)" --overwrite`),
confirm the rendered Secret changed, then verify the gateway rejects the old
key. Deleting a field alone is not revocation: if a template reference is
missing, External Secrets Operator leaves the previously rendered Secret in
place. Rotating `llm_omni` affects every omni consumer (extractors and hermes
aux), so rotate deliberately.

There is no cloud fallback — the studio is a deliberate SPOF.


MCP has no open route (see MCP Backend).


Lane-fit guidance: `omni` covers everything fidelity-sensitive: summarization, compression, session search, memory writes, OCR/vision, plus classification, tagging, title/routing decisions and short structured extraction. `agent` for AI-ops automation: alert RCA, ScheduledHealthChecks, MCP batch tool workloads. `persona` for identity-bound RP/persona chat; `uncensored` for open-ended human chat without a fixed persona.

`omni` uses **MiniCPM-O-4.5** (Apache-2.0, 9B omni: Qwen3-8B backbone + vision/audio encoders; OpenCompass 77.6, OCRBench 876) served on the studio (studio id `minicpm-o-4.5`, ~7 GB at MLX 4bit). All `fast`/`memory`/`vision` consumers (firecrawl, karakeep text+image, home-assistant-sgcc OCR, hindsight memory, trendradar digest, frigate event descriptions (native GenAI), hermes aux side-tasks) use `omni`. Not on omni: `agent` (automation main brain), `persona` (identity-bound RP), `uncensored` (open chat), embeddings/reranker (studio ids `qwen3-embedding-0.6b`/`qwen3-reranker-0.6b`). ASR: no deployment — no current consumer; when one appears, pick a lane deliberately.

### Intranet exposure

The gateway API surface is exposed to the intranet via `kgateway-internal` (10.10.0.131) at `https://api.noirprime.com` (`/v1/*`, `/mcp`; dashboard stays on `https://ai.noirprime.com/ui`):

- `/v1/chat/completions` — LLM lanes (strict API key; promptGuard on all but `uncensored` and `persona`)
- `/v1/models/<model>` — per-model direct-response discovery on the model's own route, authorized by that route's credential
- `/v1/embeddings`, `/v1/rerank`, `/v1/audio/speech`, `/v1/audio/transcriptions` — media lanes via LLM-pipeline backends (strict API key)
- `/mcp/search`, `/mcp/cluster`, `/mcp/persona`, `/mcp/agent`, `/mcp/browser`, `/mcp/github-ro`, `/mcp/github-pr` — tiered MCP routing (per-tier API key; mcp-guardrails ExtMCP on the search + github-ro + agent + browser + github-pr tiers, FailClosed)
  (dashboard UI lives separately at `https://ai.noirprime.com/ui`)

TLS terminates at kgateway (cert-manager `noirprime-com-tls`, wildcard `*.noirprime.com`); external-dns auto-creates the AdGuardHome record. Machine clients authenticate with agentgateway API keys — no SSO extAuth on API paths. Reachable from trusted VLANs (10/100/200); IoT VLAN 210 is ACL-blocked from RFC1918.

### App → model lane

| App                  | Lane              | Model              | Notes                                                        |
| -------------------- | ----------------- | ------------------ | ------------------------------------------------------------ |
| hermes-agent         | `agent`           | Ornith-1.5-35B | Agent brain: automation / KB QA / ops batching; aux side-tasks on `omni` (GitOps configmap) |
| robusta (holmes)     | `agent`           | Ornith-1.5-35B      | Alert RCA + ScheduledHealthChecks; 32K client context cap bounds oMLX prefill memory; temperature 0.6 per model tuning |
| hindsight            | `omni`            | MiniCPM-o 4.5      | Extraction-dominant (single-model constraint); embeddings + reranker via gateway media routes |
| firecrawl            | `omni`            | MiniCPM-o 4.5      | Batch page extraction/summarization                          |
| karakeep             | `omni`            | MiniCPM-o 4.5      | Text + image tagging (unified); embeddings via `/v1/embeddings` (model `embedding`, 1024d) |
| trendradar           | `omni`            | MiniCPM-o 4.5      | News digest (`openai/omni`); queryable via the `search` MCP tier |
| home-assistant-sgcc  | `omni`            | MiniCPM-o 4.5      | Meter/bill photo OCR                                         |
| dsh-tavern           | `persona`         | Orion-26B-A4B-v1.1 | RP portal (dsh-tavern image); provider/key GitOps-managed via `llm_persona` |
| dsh-web              | `uncensored`/`deepseek` | Qwen3.8-27B / DeepSeek | Agent workbench (servitor-apps); shared provider + search/cluster MCP tiers |
| open-webui           | `uncensored`      | Qwen3.8-27B        | Human chat portal; search-tier MCP and OTEL traces |

Both DSH apps also expose DeepSeek through `DEEPSEEK_API_KEY`. It is a direct external provider, not an agentgateway lane, and does not override the default model.

All `omni` consumers (extractors + hermes aux) ride the **guarded**
`/v1` route for that model; their prompts carry scraped web content, so a low rate of
promptGuard false-positive rejections (403) is expected and watched — see
the TODO table. Bare `jailbreak`/`越狱` are allowed as topical terms;
direct self/model instructions and structured role-hijacking or mode-switch
phrases remain rejected on both `agent` and `omni`.

### MCP Backend — tiered, guarded, no open lane

One gateway route per ToolHive group, each with its **own credential** —
group ↔ route ↔ key are bound 1:1:1 (every rule rewrites its tier prefix to
the canonical `/mcp` upstream):

| Route          | vmcp          | Servers (aggregated)                                          | Key (1Password `agentgateway`) | Issued to                    |
| -------------- | ------------- | ------------------------------------------------------------- | ------------------------------ | ---------------------------- |
| `/mcp/search`  | `vmcp-search` | firecrawl, context7, trendradar                               | `mcp_search`                   | hermes, open-webui, dsh-web     |
| `/mcp/cluster` | `vmcp-cluster`| kubernetes, fluxcd, grafana, victoria-logs/-metrics/-traces   | `mcp_cluster`                  | hermes, dsh-web                      |
| `/mcp/github-ro` | `vmcp-github-ro` | github-ro (read-only mode + lockdown; repos/issues/pull_requests) | `mcp_github_ro`            | hermes |
| `/mcp/persona` | `vmcp-persona`| home-assistant, hindsight persona bank                        | `mcp_persona`                  | none (reserved)                      |
| `/mcp/agent`   | `vmcp-agent`  | forgejo (ticket RW), hindsight-ops bank                       | `mcp_agent`                    | hermes, external operator agents |
| `/mcp/browser` | `vmcp-browser`| playwright (Chromium via pod-local CDP proxy)                 | `mcp_browser`                  | none (reserved)                    |
| `/mcp/github-pr` | `vmcp-github-pr` | github-pr (branch/commit/create PR, no merge)              | `mcp_github_pr`                | none (reserved)                    |

A key minted for one group is invalid on every other route — this is what
scopes the search consumer to search and keeps chat-tier consumers out of incident
memory and the tickets repo. The read-only GitHub server was split out of
`search` into its own `github-ro` tier so cluster-tier consumers can hold code
retrieval without the web-retrieval toolsets; `search` no longer exposes GitHub.
`search` is held by hermes, open-webui, and dsh-web; `cluster` by hermes and
dsh-web; `github-ro` by hermes only. Persona, browser, and github-pr remain
defined but are unused.
The persona group uses the `mcp_persona` credential. It now aggregates only
Home Assistant and the Hindsight `persona` bank; the `home`/`work`/`others`
proxies were removed. `mcp_agent` is never distributed to in-cluster
chat apps. **Grouping rule:** create a group only for a new consumer or a
new permission class; a new server joins the matching existing group.

**Tool filtering** lives at the gateway (`backend.mcp.authorization` CEL,
Allow = default-deny; `config/mcp/filters.yaml`), not toolhive — toolhive's
filter middleware is broken for vmcp Modern backends (SEP-2322 envelope
loss, 2026-10-10). Only servers without an upstream token boundary are
CEL-filtered (firecrawl, trendradar, grafana, victoria-metrics); github,
forgejo, kubernetes, fluxcd are bounded by their upstream tokens/SAs and
full-allowed by prefix. Allowlists are version-tracked: each filtered
server's `mcpserver.yaml` names the image tag the tool names were
enumerated from (live, 2026-10-20) — re-verify on every renovate bump.
This requires the vmcp **optimizer to stay off**: it masks real tool names
behind `find_tool`/`call_tool` meta-tools that gateway authorization cannot
see through (removed 2026-10; also dropped the vmcp embeddings dependency).

The **search, github-ro, agent, browser and github-pr backends** carry the mcp-guardrails ExtMCP sidecar
(agentgateway `mcp.guardrails`): `tools/call` is scanned request+response,
`tools/list` skips the response scan on all five tiers (the catalog is
operator-authored config, not untrusted content), while `prompts/get` /
`resources/read` stay response-only;
`failureMode: FailClosed` (the sidecar being down disables those five tiers
rather than passing them unguarded). The 1.4.0 LoopRule evaluates only the
newest call fingerprint: historical retry triads cannot deny new tools or
arguments, while identical retries still block. This prevents denied attempts
from permanently locking a trace. Scope decision (2026-10-20): search is
the tier where untrusted web content reaches an unguarded lane (dsh-tavern /
any `uncensored`- or `persona`-lane consumer). Hermes rides the guarded
`agent` LLM lane, and the ExtMCP sidecar additionally scans MCP tool content
because forgejo ticket bodies carry alert/log-derived (untrusted) strings.
DSH Web now uses only the unguarded `uncensored` lane or direct DeepSeek and
the search/cluster tiers; those LLM calls are not covered by the agent
promptGuard. The browser and github-pr tiers have no current consumer. The
cluster tier (hermes) adds CEL allowlists and token/SA boundaries; the
persona tier is RW-by-design behind the HA token. Neither carries
the ExtMCP sidecar; both still require per-route API keys and retain their
CEL/RBAC/token boundaries. No MCP route is unauthenticated.
Response scanning uses four balanced windows (11KiB
by default) with a 3.5s scanner deadline and a 15s Service-scoped ExtMCP
callout deadline; readiness completes a full-size warmup before traffic.
There is deliberately **no** unguarded MCP route. Direct vmcp
access is cilium-restricted to the gateway federation and vmagent metrics
(exception: `kubectl port-forward` reaches the anonymous vmcp endpoint by
design of the kubelet path — acceptable, it is RBAC-gated; harden via vmcp
`incomingAuth` if that ever changes).
---

## LLM Inference — Local

All lanes run on the MacStudio inference host (`uncensored` Qwen3.8-27B, `persona` Orion-26B-A4B-v1.1 4-bit, `agent` Ornith-1.5-35B, `omni` MiniCPM-o 4.5). The in-cluster llama.cpp deployment (`llama-qwen3`) was archived 2026-08-28; its 50Gi CephFS PVC `llama` is retained for manual cleanup. Qwen3.5-4B was retired 2026-09-09 with the `fast`/`memory`/`vision` lane removal.

---

## AI Agent Platform

### Hermes Agent

Runs `ghcr.io/soulwhisper/hermes-agent` — the upstream image plus baked
extras (rtk, caveman skills, feishu deps), supervisord-managed `gateway` +
`dashboard` in one container. Tag tracks upstream semver releases.

| Component | Port | Notes                       |
| --------- | ---- | --------------------------- |
| Dashboard | 9119 | SSO-protected               |
| Gateway   | 8642 | Internal; probes require `/health` plus a current cron heartbeat |

- **Runtime**: user namespaces (`hostUsers: false`) + RuntimeDefault seccomp + egress CNP (ADR-03; Kata removed)
- **Resources**: req: 200m CPU / 1Gi RAM, lim: 4Gi RAM
- **Integrations**: Feishu (plugin `plugins/platforms/feishu`, WebSocket mode, the only messaging platform), Firecrawl (internal), ToolHive MCP (`search`+`cluster`+`agent` tiers in the ops profile; the default profile has no MCP access), Agent Gateway LLM
- **Egress**: CiliumNetworkPolicy — agentgateway-proxy:80 (L7: POST `/v1/*` + `/mcp/*` only), kube-dns, world-except-private :443 restricted to TLS SNI `open.feishu.cn` (Feishu WebSocket). No direct vmcp access — MCP goes through the guarded tiered `/mcp/*` endpoints like every other client
- **Ingress**: caller-scoped CNP (#3934) — dashboard :9119 + webhook ingest :8644 via kgateway-internal (shared rule), webhook ingest :8644 also from frigate + LAN, profile API :8642 same-namespace only; `fromEntities: host` keeps kubelet probes working
- **Depends on**: `agentgateway` (Flux dependency)
- **Profiles** (seeded declaratively by the `seed-config` initContainer from `configmap.yaml`; dashboard edits to `config.yaml`/profile files revert on restart):
  - `ops` — the batching brain: cron/Feishu/automation workload lives here (search, cluster read-only, and agent ticket/incident-memory MCP tiers); owns the Feishu adapter, credentials, home channel and new Feishu sessions
  - `default` — fallback/scratch with no Feishu adapter and no MCP servers (chat through the provider only); the retired `chat` profile was removed 2026-10 when the human interface moved to dedicated portals
  Model/provider config (`model.provider: custom` → agent gateway, `model.default: agent`) and aux side-tasks (`vision`/`web_extract`/`session_search`/`compression`/`title_generation` → `omni`) are GitOps-managed in `configmap.yaml`; the gateway's PreRouting transformation maps body `model` → `x-model` header, so lane names are model names. The main brain uses `OPENAI_API_KEY` (`llm_agent`); each aux task selects `OPENAI_AUX_API_KEY` (`llm_omni`) via `key_env`, so the agent key is never accepted on the omni route. Requires 1Password `hermes-agent` field: `api_server_key_root` (>=16 chars)

---

### Open WebUI

- Human chat portal, image `ghcr.io/open-webui/open-webui`. Lives in **servitor-apps**
- **Auth**: Authentik forward-auth gates access at the gateway; with no trusted-header mapping, Open WebUI login is disabled and requests use its shared local system account
- **Ingress**: `chat.noirprime.com` via kgateway-internal
- **LLM**: single agentgateway OpenAI provider; `uncensored` only. The admin connection sets `model_ids` to `[uncensored]`; open-webui does not use the `omni` lane or hold an omni credential. Existing installations must save the same `model_ids` in the admin UI before the global catalog is removed.
- **MCP**: native search-tier connection through `/mcp/search` with the `mcp_search` bearer key
- **State**: shared CNPG for app data and pgvector, app Dragonfly for session/rate-limit state, and the `open-webui` Ceph bucket for uploads and KB files; the entire data directory is rewarmable cache on the `open-webui-cache` ceph-cache PVC
- **Egress**: agentgateway, CNPG, Dragonfly, Ceph RGW, OTLP collector, kube-dns, and world-except-private for RAG fetching

### DSH Web

- Agent workbench, image `ghcr.io/soulwhisper/dsh-web` (DSH Web + `dshmarket` + required forward-auth). Lives in **servitor-apps**
- **Auth**: Authentik forward-auth at the gateway; the blueprint owns group authorization. The app consumes the stable owner subject from the `app-user` ExternalSecret and no longer references Authentik groups. No startup-token or local-password fallback
- **Ingress**: `dsh.noirprime.com` via kgateway-internal
- **State**: kopiur-backed PVC `dsh-web` at `/data`; `/workspace` is a subPath on the same claim. `/cache`, `/logs` and `/backups` share the `dsh-web-cache` `ceph-cache` PVC; `/tmp` remains emptyDir
- **MCP/Skills**: the `dsh-web` ExternalSecret carries one host `cordis.patch.yml` for the shared `uncensored` provider plus the search and cluster MCP tiers (`/mcp/search`, `/mcp/cluster`). There is no writable profile seed or profile-patch init container; the MCP panel reads the host patch. MCP bearer keys are injected by External Secrets into the host patch, never stored in Git. MCP startup remains non-fatal, and both tiers reconnect from 1s to a 30s ceiling with no practical attempt cap so long backend outages do not require a DSH restart. Native skill roots are `<workspace>/.dsh/skills`, `<workspace>/.agents/skills`, `$DSH_HOME/skills` and `$DSH_AGENTS_HOME/skills`; register `/workspace` as the DSH workspace, not `/data/home`.
- **Mnemon**: runs inside DSH Web, not as a separate Deployment or CRD. It has no Hindsight persistence provider configured; `writeEnabled` stays on and any memory provider or Memory Space is configured in the UI and persists on the `dsh-web` PVC. No bank is pinned by GitOps.
- **LLM/MCP**: UI-selectable agentgateway `uncensored` and DeepSeek providers; MCP uses the guarded search/cluster tiers. No default model is pinned
- **Egress**: CiliumNetworkPolicy — agentgateway-proxy:80 (`/v1/*` + `/mcp/(search|cluster)*`), world-except-private :443 for direct DeepSeek LLM calls and the user-driven plugin market, kube-dns

### DSH Tavern

- RP chat portal, image `ghcr.io/soulwhisper/dsh-tavern` (dsh-tavern profile + eco plugins baked). Lives in **servitor-apps**
- **LLM**: GitOps-managed `persona` gateway lane (`llm_persona`, Orion-26B-A4B-v1.1 4-bit) plus DeepSeek via `DEEPSEEK_API_KEY`; no default model is pinned
- **Auth**: Authentik forward-auth at the gateway; the blueprint owns group authorization. The app consumes the stable owner subject from the `app-user` ExternalSecret and no longer references Authentik groups. No startup-token or local-password fallback
- **Ingress**: `tavern.noirprime.com` via kgateway-internal
- **Egress**: CiliumNetworkPolicy — agentgateway-proxy:80 (LLM only), world-except-private :443 for direct DeepSeek LLM calls, card/preset fetches and tavern-image backends, kube-dns
- **State**: kopiur-backed PVC `dsh-tavern` at `/data`; `/workspace` is a subPath on the same claim. `/cache`, `/logs` and `/backups` share the `dsh-tavern-cache` `ceph-cache` PVC; `/tmp` remains emptyDir

### Media lanes (studio-hosted, OpenAI-compatible)

Non-chat vector modalities run on the same oMLX process as the chat lanes, exposed through independent per-model HTTPRoutes and authentication policies. Embeddings and reranker use `custom` providers declaring exactly one API format; audio uses explicit passthrough routes. Each media credential uses its own field in the shared `agentgateway` 1Password item (`llm_embedding`, `llm_reranker`, `llm_audio`):

| Path             | Backend             | Client model | Upstream (override)      | Model                                   | Timeout |
| ---------------- | ------------------- | ------------ | ------------------------ | --------------------------------------- | ------- |
| `/v1/embeddings` | `studio-embedding` | `embedding`  | `qwen3-embedding-0.6b`   | Qwen3-Embedding-0.6B (1024d)            | 120s    |
| `/v1/rerank`     | `studio-reranker`  | `reranker`   | `qwen3-reranker-0.6b`    | Qwen3-Reranker-0.6B (Cohere-compatible) | 120s    |
| `/v1/audio/speech`, `/v1/audio/transcriptions` | `studio-audio` | `voxcpm2` | (passthrough — no override) | VoxCPM2 (TTS) | 300s |

The ComfyUI `image`/`voice` lanes (`:8001`) stay retired — plain passthrough gains nothing from gateway policy; the qwen-image-2.1 download remains parked. `/v1/audio/transcriptions` (ASR) is wired on the audio backend but has no consumer yet. Passthrough applies no LLM parsing — the audio lane has no model override, so clients send the folder id `voxcpm2` (unlike embeddings/rerank aliases).

Config: `kubernetes/apps/networking-system/agentgateway/config/media/` — backends + per-model routes on `agentgateway-proxy`. Clients use `https://api.noirprime.com` as base URL with their capability key (`llm_embedding` for karakeep/hindsight embeddings, `llm_reranker` for hindsight rerank, `llm_audio` for future audio consumers) — each media backend injects the oMLX server key upstream via `policies.auth.secretRef: studio-api-auth`, identical to the chat lanes (the studio key is held by the backends and a read-only `blackbox-exporter` copy for direct probes; it is not issued to lane consumers). **Consumers**: embeddings — karakeep, hindsight; rerank — **hindsight only**; audio — none yet (TTS lane ready). The direct-to-studio blackbox probe reads the oMLX key via `credentials_file` — API-plane only (`GET /v1/models`): per-model inference probes were removed because oMLX auto-loads models and evicts KV on TTL. karakeep and hindsight vector stores were rebuilt for the 0.6B/1024d embedding space (no data was preserved).

---

## MCP Gateway

### ToolHive

- **Operator**: namespace-scoped RBAC
- **Variant layout**: `mcp/hindsight/{app,persona,ops}` and `mcp/github/{app,ro,hr}`; each `app` is a shared Kustomize base, while sibling directories are independently reconciled overlays
- **7 Virtual MCP Servers** (search / cluster / github-ro / persona / agent / browser / github-pr) with:
  - Circuit breaker (3 failures → 30s timeout)
  - OTEL telemetry (5% sampling)
  - **No optimizer** (removed 2026-10): it hid real tool names behind
    `find_tool`/`call_tool` meta-tools, blocking gateway-level tool
    filtering; its removal also dropped the vmcp embeddings dependency
  - Daily restarter CronJob caps the runner's ~9Mi/h streamable-http leak
    across all seven groups (homelab-tickets#59)
- **Ingress restricted**: only agentgateway-proxy (MCP protocol, tiered `/mcp/*`) and vmagent (metrics scrape) can connect; chat frontends reach tools through the gateway, never directly

### MCP Servers (16 total)

#### search (web/docs/news/codebase retrieval — hermes, open-webui, dsh-web)

| Server    | Transport             | Notes                    |
| --------- | --------------------- | ------------------------ |
| firecrawl | Streamable HTTP :8080 | Local Firecrawl instance; gateway-filtered to retrieval tools |
| context7  | stdio :3000           | Context7 API (2 read tools) |
| trendradar | Streamable HTTP :8080 (proxy→:3333) | TrendRadar news DB; gateway-filtered to query/analysis (no trigger/notify) |

#### github-ro (read-only code retrieval — hermes)

| Server    | Transport     | Notes                                                                 |
| --------- | ------------- | --------------------------------------------------------------------- |
| github-ro | HTTP :8082    | `GITHUB_READ_ONLY=1` + lockdown, toolsets repos/issues/pull_requests; uses the shared GitHub PAT from `github-keys` (same credential as github-pr) and keeps the FailClosed injection scan. Split from `search` so cluster-tier consumers can hold it without the web-retrieval toolsets. |

#### cluster (read-only, no egress — hermes, dsh-web)

| Server        | Transport             | Connects To                   |
| ------------- | --------------------- | ----------------------------- |
| kubernetes    | HTTP :8080            | kube-apiserver (read-only SA) |
| fluxcd        | HTTP :9090            | Flux (read-only SA)           |
| grafana       | Streamable HTTP :8000 | Grafana (read-only SA + `--disable-write`; gateway-filtered: no `grafana_api_request`/manage/provisioning) |
| victoria-logs | Streamable HTTP :8081 | VictoriaLogs                  |
| victoria-metrics | Streamable HTTP :8081 | VictoriaMetrics; gateway-filtered to the query surface |
| victoria-traces | Streamable HTTP :8081 | VictoriaTraces                |

Grafana MCP receives a Grafana `Viewer` token through the
`mcp-grafana-sa` ExternalSecret. The source Secret lives in
`monitoring-system`; the Kubernetes SecretStore reads it as
`security-system/eso-kubernetes` and ESO writes the copy in `servitor-apps`.
The CA ConfigMap is read using the ESO controller's identity, not that
provider ServiceAccount.

The source token's Role and RoleBinding belong only to `grafana-cluster`.
The External Secrets integration owns the provider ServiceAccount and
ClusterSecretStore. `security-system/external-secrets-cluster` declares only
`security-system/external-secrets` in its Flux `dependsOn`. At runtime, the
store also requires the Grafana-owned Role and RoleBinding in
`monitoring-system` to read source Secrets. The MCP consumer depends on
that store, Grafana, and ToolHive configuration; this does not add an
infrastructure-to-monitoring Flux dependency.

For an RBAC ownership handoff, apply object-level prune protection to
`monitoring-system/Role/eso-store-role` and
`monitoring-system/RoleBinding/eso-kubernetes-store-role` in both declaring
Kustomizations: `monitoring-system/grafana-cluster` and
`security-system/external-secrets-cluster`.

For each stage, record its actual merge commit SHA, not the PR branch head.
Before advancing, require both Kustomizations to report that exact Git SHA
in `status.lastAppliedRevision`, `Ready=True`, and
`status.observedGeneration == metadata.generation`. A stale Ready condition
or an applied revision without current readiness does not pass this gate.

Remove the duplicate declaration only after the protection-stage gate
passes and both live RBAC objects carry the prune protection. Remove the
protection only after the ownership-change-stage gate passes, only
`monitoring-system/grafana-cluster` inventories both objects, and neither
appears in `security-system/external-secrets-cluster`'s inventory. Verify
both objects retain their pre-handoff UIDs and token synchronization stays
healthy. After restoring pruning, use the same gate for that stage's merge
SHA and verify the protection is absent, ownership remains unique, and
UIDs and token synchronization are unchanged. Keep Kustomization pruning
enabled throughout.

#### persona (read-write, no egress — no current consumer)

| Server            | Transport            | Connects To            |
| ----------------- | -------------------- | ---------------------- |
| home-assistant    | HTTP (FastMCP) :8086 | Home Assistant         |
| hindsight-persona | HTTP proxy :8080     | Hindsight `persona` bank (single-bank MCPToolConfig) |

#### agent (operator agents only)

| Server       | Transport             | Notes                                       |
| ------------ | --------------------- | ------------------------------------------- |
| forgejo      | Streamable HTTP :8080 | Forgejo on nas:9003 via forgejo-mcp; forwarded repo-scoped `pat_tickets` — the Forgejo-side token scope is the security boundary (no CEL) |
| hindsight-ops | Streamable HTTP :8080 (proxy→:8888) | Hindsight `ops` bank; incident/RCA memory, no chat-tier consumers |

Forgejo's `pat_tickets` retains repository-write scope for the manual lessons
workflow, so the guard is the token's Forgejo-side permission scope itself.
A model-facing `MCPToolConfig` allowlist was tried and removed the same day
(2026-10-10): toolhive v0.51.4's filter middleware re-encodes `tools/list`
through a lossy struct that strips the SEP-2322 `resultType` envelope, which
vmcp rejects for Modern-era backends — the forgejo backend circuit-broke out
of its group until the filter was dropped. Permission filtering now lives at
the gateway where needed (see filters.yaml); toolhive `MCPToolConfig` is
kept ONLY for the hindsight banks' description overrides. No draftbox or
broad user PAT was provisioned.

#### browser (no current consumer)

| Server     | Transport             | Notes                                       |
| ---------- | --------------------- | ------------------------------------------- |
| playwright | Streamable HTTP :8931 | Connects over CDP to the separate `playwright` Chromium workload on :9222; renderer HTTP(S) is forced through a loopback-only Squid that denies loopback/private/CDP destinations while CDP control stays on a separate nginx channel. `TMPDIR=/tmp/playwright` places `pw-<hash>` browser socket directories on the writable emptyDir, `XDG_CACHE_HOME=/tmp/playwright/.cache` covers MCP initialization cache, `HOME=/tmp/playwright` covers environment-based paths, and an emptyDir at `/home/node` keeps relative screenshot/console/network/evaluate filenames writable despite the read-only root filesystem |

The browser vmcp also mounts an `emptyDir` at `/tmp`: it runs with
`HOME`/`XDG_CONFIG_HOME=/tmp` and a read-only root filesystem.

#### github-pr (no current consumer)

| Server    | Transport     | Notes                                                                  |
| --------- | ------------- | ---------------------------------------------------------------------- |
| github-pr | HTTP :8082    | Shared scoped `mcp_github_token`; file/commit/PR reads, branch list/create, file writes and PR creation; no merge |

#### Obsidian facts workflow

Plain-text pipeline, no extra copies: Obsidian → Dropbox (canonical; its own sync/revisions) → Synology CloudSync pull → `/volume1/backup` on the NAS. Agent-authored notes never write into the vault copy; they currently have no versioned landing zone — promotion into the vault is manual.

---

## LLM Observability

### Langfuse

| Component | Image                                      | Resources            |
| --------- | ------------------------------------------ | -------------------- |
| web       | `ghcr.io/langfuse/langfuse`        | req: 1 CPU, lim: 2Gi |
| worker    | `ghcr.io/langfuse/langfuse-worker` | req: 1 CPU, lim: 4Gi |

- **Deployment**: one Pod with `app` (web) and `worker` containers sharing the `langfuse` application identity
- **Backends**: ClickHouse (analytics), Dragonfly Redis (cache/queue), Ceph S3 (events/exports), CloudNativePG (metadata)
- **Features**: Experimental features enabled, telemetry disabled

---


### TrendRadar

- AI news digest pipeline (selfhosted-apps): community hot-list (47 sources, issue #95) + custom RSS watch list (aiera.com.cn, expreview.com + GitHub Atom placeholders); `report.mode: incremental` (zero-duplicate push), keyword grouping (科技 topic covers both portals), AI analysis via gateway (`openai/omni`)
- Delivery: Feishu custom group robot (`FEISHU_WEBHOOK_URL` from 1Password `feishu.newsbot_webhook`); HTML report at `news.noirprime.com` (SSO)
- MCP server (:3333) registered as `trendradar` in the `search` group (gateway-filtered to query/analysis tools; consumed by hermes, open-webui, and dsh-web)
- Config fully in ConfigMap (`config.yaml` + `frequency_words.txt` + `ai_interests.txt`); output on 1Gi ceph-block PVC

## AI-Adjacent Services

### Vision alerting (frigate-vision)

Frigate is the 24/7 trigger layer AND the event describer: 0.18 native GenAI (`objects.genai`, multi-frame, per-camera/object prompts) runs on an openai-compatible provider pointed at the `omni` lane (MiniCPM-o 4.5, `descriptions` role). The caption prompt instructs the model to start with a `[low|medium|high]` severity prefix. Frigate config (provider + per-camera GenAI toggle) lives in the Frigate UI/DB — it is not GitOps-managed. `smarthome-apps/frigate-vision` is a slim forwarder only (python, ConfigMap-mounted): MQTT `frigate/tracked_object_update` (`type: description`) → parse severity prefix → gate on `MIN_SEVERITY` (default medium) → enrich via frigate `GET /api/events/{id}` → hermes webhook `POST :8644/p/ops/webhooks/frigate-alert` (V2 HMAC) — the `ops` profile ingests it as a user message, so the batching brain sees camera events in context with everything else it knows. Webhook route is declared in the GitOps-managed default `config.yaml` (`platforms.webhook.extra.routes`, HMAC secret via `FRIGATE_WEBHOOK_SECRET` in 1Password). The HA `persistent_notification` leg is an HA-side MQTT automation on the same description messages (UI-managed, not GitOps). 1Password additions: `hermes-agent.webhook_secret_frigate`.

### Firecrawl

- Web scraping pipeline for AI data ingestion
- 3 containers: api (:3002), nuq-worker (:3006), playwright-service (:3000)
- `ghcr.io/firecrawl/firecrawl` (api + nuq-worker; playwright-service pinned by digest), sandboxed per ADR-03 (`hostUsers: false` + egress CNP)
- Network: egress CNP plus default-deny ingress allowing ToolHive MCP and blackbox scrape/search canaries on `firecrawl-app:3002`, kubelet health probes, and internal Firecrawl callers to Playwright on `:3000`; ingress rules enable ingress default-deny, while egress-only selection does not restrict ingress
- Backed by SearXNG, Dragonfly Redis, nuq-postgres
- Exposed as MCP server + internal endpoint for Hermes

### Hindsight

- AI memory / context store (agent long-term memory: retain / recall / reflect)
- Image: upstream `ghcr.io/vectorize-io/hindsight` (slim variant) — no in-process local-ml
- LLM: `omni` lane → **MiniCPM-O-4.5 on the MacStudio** (via agentgateway `/v1/chat/completions`)
- Embeddings: **Qwen3-Embedding-0.6B on the MacStudio** (oMLX id `qwen3-embedding-0.6b`, 1024d) via gateway `/v1/embeddings`; store rebuilt from scratch for the 0.6B space
- Reranker: **Qwen3-Reranker-0.6B on the MacStudio** (Cohere-compatible, id `qwen3-reranker-0.6b`) via gateway `/v1/rerank`
- Resources: req: 200m CPU / 512Mi, lim: 2 CPU / 2Gi
- Storage: CloudNativePG (vchord vector + pgroonga text search), OTEL enabled
- Exposed as MCP server for agent context retrieval

### Archived

- **Buzz** (relay + buzz-agent-omp) — buzz-agent-omp removed 2026-08-28; buzz-relay removed 2026-09-09, superseded by hermes' native webhook ingestion (`/p/<profile>/webhooks/<route>`, HMAC); manifests deleted from git. Its CNPG DB, Dragonfly, and Ceph bucket are retained in-cluster for manual cleanup.
- **Fast-Note-Sync** — removed 2026-09-09, manifests deleted from git; the draftbox-via-forgejo-MCP successor was never implemented and is dropped. Dropbox MCP was evaluated and rejected (beta, DCR-limited clients, short-lived tokens, cloud round-trip for local data)
- **Devbox** — removed from cluster 2026-08-05; image retained in `soulwhisper/containers` as an ad-hoc exec sandbox.
- **llama.cpp (llama-qwen3)** — archived 2026-08-28; all local lanes moved to the MacStudio.

---

## Shared Infrastructure (all AI apps depend on)

| Service                     | Namespace           | Purpose                                             |
| --------------------------- | ------------------- | --------------------------------------------------- |
| **Agent Gateway**           | `networking-system` | LLM + MCP routing                                   |
| **CloudNativePG**           | `database-system`   | PostgreSQL + PGVector for Langfuse, Hindsight |
| **Dragonfly**               | Various             | Redis-compatible cache/queue                        |
| **ClickHouse**              | `database-system`   | Langfuse analytics                                  |
| **Ceph (Rook)**             | `storage-system`    | S3 + block + CephFS for model/data storage          |
| **Workload sandboxing**      | —                   | user namespaces + egress CNP per ADR-03 (Kata removed)  |
| **kgateway**                | `networking-system` | API gateway + SSO extAuth                           |
| **Authentik**               | `security-system`   | SSO for all public AI endpoints                     |
| **Cert-Manager**            | `security-system`   | TLS certificates                                    |
| **VictoriaMetrics**         | `monitoring-system` | Metrics for ToolHive + OTEL                         |
| **OpenTelemetry Collector** | `monitoring-system` | Traces/metrics pipeline                             |

The host-side contract. oMLX discovers models from their **folder name**
in `~/models/`; `~/.omlx/model_settings.json` assigns each one a
`model_alias`, the API-visible name. Both the alias and the folder id resolve
on direct calls, and `/v1/models` lists the alias. Chat lane names
(`uncensored`/`persona`/`agent`/`omni`) match their aliases, but each backend's
`openai.model` override still pins the folder id
(`kubernetes/apps/networking-system/agentgateway/config/llm/`). Media
lanes: clients send `embedding` / `reranker` and the media backends'
`custom.model` override rewrites them to folder ids; the audio lane is a
passthrough exception — clients send `voxcpm2` directly. Folder ids are
only needed for direct-to-studio calls.

**Auth**: oMLX enforces a server API key (1Password item `omlx`, field
`api_key`). Every backend — chat and media alike — injects it upstream via
`policies.auth.secretRef: studio-api-auth`; consumers always present a
per-lane gateway key (`agentgateway` item, `llm_<lane>` fields). The studio
key is held by the backends and a read-only `blackbox-exporter` copy in
`monitoring-system` for direct probes; it is not issued to lane consumers.

Alignment table (keep in sync with the bootstrap downloads):

| Order | Lane        | Studio id (folder)       | Model                        | HF source                                   | Format / size   | Served by |
| ----- | ----------- | ------------------------ | ---------------------------- | ------------------------------------------- | --------------- | --------- |
| 1     | `uncensored` | `qwen3.8-27b`           | Qwen3.8-27B Uncensored       | `orcarouter/Qwen3.8-27B-Uncensored-MLX`     | MLX 4bit, ~15.7G | oMLX :8000 |
| 2     | `persona`   | `orion-1.1-26b-a4b`     | Orion-26B-A4B-v1.1          | `ailexleon/Orion-26B-A4B-v1.1-mlx-4Bit`     | MLX 4bit, ~13.9G | oMLX :8000 (`agentgateway-persona-route`) |
| 3     | `agent`     | `ornith-1.5-35b-a3b`     | Ornith-1.5-35B               | DeepReinforce Ornith-1.5-35B, local MLX 4bit conversion | MLX 4bit, ~19G | oMLX :8000 |
| 4     | `omni`      | `minicpm-o-4.5`          | MiniCPM-O-4.5                | `mlx-community/MiniCPM-o-4_5-4bit`          | MLX 4bit, ~7G   | oMLX :8000 |
| 5     | `embedding` | `qwen3-embedding-0.6b`   | Qwen3-Embedding-0.6B (1024d) | `mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ` | MLX, ~1.3G    | oMLX :8000 (`/v1/embeddings`) |
| 6     | `reranker`  | `qwen3-reranker-0.6b`    | Qwen3-Reranker-0.6B          | `mlx-community/Qwen3-Reranker-0.6B-4bit`    | MLX, ~1.3G      | oMLX :8000 (`/v1/rerank`) |
| 7     | `audio`     | `voxcpm2`                | VoxCPM2                      | `mlx-community/VoxCPM2-4bit`              | MLX 4bit        | oMLX :8000 (`/v1/audio/speech`) |

oMLX aliases: `uncensored`, `persona`, `agent`, `omni`, `embedding`,
`reranker`, `voice` (`voxcpm2`), and `image` (`qwen-image-2.1`, not
discovered by oMLX 0.7). `persona` is the renamed 4-bit Orion conversion and
is consumed by dsh-tavern through `llm-persona-auth` / `llm_persona`.

oMLX reports context windows via `/v1/models`: `uncensored`/`persona`/`agent`
65536, `omni`/`reranker` 40960, `embedding`/`voice` 32768. DSH provider
entries declare the matching `contextWindow`. The host `cordis.patch.yml`
cannot override the nested `compaction-basic` inside the active agent preset;
apply the 64K policy in the selected preset (Agent presets UI or a custom
preset) with `thresholdRatio: 0.75`, `headroomTokens: 8192`,
`retainTokens: 4096`, per-model policies, and a local summarizer. Until that
preset is selected, use `/compact` or a bounded handoff before a 64K lane.
Moving a long cloud-model analysis to a 64K lane must use a bounded handoff
brief, not the same session with raw tool output.

Downloaded but **parked — no lane, no consumers** (re-add deliberately
when a consumer appears; see Media lanes):

| Studio dir (`~/models/`) | Model            | HF source                                 | Intended role |
| ------------------------ | ---------------- | ----------------------------------------- | ------------- |
| `qwen-image-2.1`         | Qwen-Image 2.1   | `abenzerps/Qwen-Image-2.1-Uncensored-GGUF` (ComfyUI int8 safetensors) | image gen (oMLX alias `image`; model type not discovered by oMLX 0.7, so inert) |

Host prerequisites (out of band): models present at `~/models/<folder>`
with folder names exactly as the Studio id column (bootstrap
`hf download --local-dir`). (Retired: ComfyUI `image`/`voice` on :8001 —
see Media lanes.)

## Non-unified Configuration & TODO

Routes and configs not yet unified under the agent gateway, plus deferred
items:

| Item | State | Path forward |
| ---- | ----- | ------------ |
| open-webui MCP bearer key rollout | Restored with the native search-tier bearer connection | Smoke-verify a native tool call after rollout; check the `tool_server.connections` config row if the persisted shape diverges |
| promptGuard FP rate on extractor traffic | Extractors (firecrawl/karakeep/trendradar/hindsight/ha-sgcc) ride the guarded lane with scraped web content in-prompt | Watch gateway 403 rates via langfuse/logs; if painful, expose `omni-raw` (one unguarded rule) as the designed escape hatch |
| hermes MCP server endpoints | Done: the ops profile covers search, cluster, and agent tiers; the default profile has no MCP access | Watch ops-profile tool calls |
| SillyTavern endpoints | UI-managed, no repo manifests | Self-managed surface; listed for completeness |
| mcp-guardrails P2 (audit volume, explicit HUMAN_REVIEW_MODE) | Deferred, on watch via langfuse decision spans (open-webui and hermes both emit OTEL) | Revisit on the first FP/rejection report; a sidecar outage fail-closes ALL tool traffic — accepted blast radius |
| ASR/TTS model | VoxCPM2-4bit served on the studio via `/v1/audio/speech` and `/v1/audio/transcriptions` (`studio-audio` backend) — lane ready, no in-repo consumer | Point a consumer at the lane when one appears; ASR (`/v1/audio/transcriptions`) wired but unused |
| backend upstream auth | `policies.auth.secretRef: studio-api-auth` on all chat + media backends (oMLX server key, ES item `omlx`) | Verify at rollout: `/v1/chat/completions` and `/v1/embeddings|rerank|audio` answer 200 through the gateway while oMLX 401s keyless direct calls |

## Model Routing Summary

```
/v1/chat/completions  (strict API key)
            │  model:
            ├─ uncensored   (OPEN)    ─► qwen3.8-27b        ── open-webui
            ├─ persona      (OPEN)    ─► orion-1.1-26b-a4b  ── dsh-tavern
            ├─ agent        (guarded) ─► ornith-1.5-35b     ── hermes, holmes, automation
            ├─ omni         (guarded) ─► minicpm-o-4.5
/v1/embeddings /v1/rerank /v1/audio/speech /v1/audio/transcriptions  (media: alias ─► override ─► folder id; audio: direct)
/v1/models/<model>  (alias or folder id; single-object direct response)

/mcp/search /mcp/cluster /mcp/github-ro /mcp/persona /mcp/agent /mcp/browser /mcp/github-pr  (per-tier key; guardrails ExtMCP on search+github-ro+agent+browser+github-pr, FailClosed) ── every MCP client
```

Agentgateway-managed routing remains internal and centralized for auth, routing, guardrails, and observability. The UI-selected external DeepSeek provider is an explicit exception for its direct LLM calls; MCP still goes through the gateway.
