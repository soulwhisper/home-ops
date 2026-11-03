# Forgejo ai-ops ticket layer (GitOps-tracked)

Truth for the **static content** of the `homelab-tickets` repo on Forgejo
(`nas.homelab.internal:9003`). Two kinds of files live here:

| Dir | Syncs to | Content |
|---|---|---|
| `skills/` | `homelab-tickets/skills/` | Ticket conventions, acceptance criteria, lessons format |
| `workflows/` | `homelab-tickets/.forgejo/workflows/` | Repo workflows (manual dispatch only — no cron, no auto-fixers) |

**Not tracked here** (by design): the tickets themselves (Forgejo issues) and
`learnings/` (agent-written memories). Those are data; they live and die in
the tickets repo and are covered by NAS backup, never by this repository.

Ticket intake is implemented by the webhook-relay's single, serialized consumer
(`kubernetes/apps/monitoring-system/webhook-relay/app/ticket_consumer.py`), not a
direct POST-per-finding sink. It is runtime code, so it stays with its Pod and
CI tests here; the tickets repo only holds static docs and workflows. Durable
incident/event markers provide indexed (search-hint, full-scan fallback)
lookup and replay suppression. Human merge and failure intervention remain required. Closure and lessons dispatch may be manual or evidence-gated through an explicitly merged post-merge plan; no autonomous fixer or complete API audit history is implied.

## Sync

This repo is the source of truth; after editing `skills/` or `workflows/`, run
`just forgejo sync`. It mirrors both dirs into the tickets repo (`skills/`,
`.forgejo/workflows/`) and pushes one commit, authenticating with
`$FORGEJO_TOKEN_FILE` (default `~/forgejo_tickets.key`) or 1Password
`forgejo.pat_tickets`. GitHub CI cannot reach the intranet NAS, so sync is an
operator step. The tickets repo also tracks `learnings/` — written by the
lessons workflow, never by sync; the recipe does not touch it.

The lessons workflow needs two repository Actions secrets in the tickets repo:
`TICKETS_TOKEN` (`pat_tickets`; Forgejo reserves the `FORGEJO_`/`GITEA_`
prefixes) and `LLM_API_KEY` (`agentgateway.llm_agent`). `TICKETS_TOKEN` must
permit API reads, source-ticket comment writes, and Git pushes. For a keyed
supervised dispatch, ordinary lesson success requires the pushed Git file's
exact `aiops_action` **and** `aiops_run` frontmatter. `NO_LESSON` success
instead requires all three parts in the same source-ticket comment:
`<!-- aiops-no-lesson -->`, the exact `aiops-action` marker, and the exact
`aiops_run: <RUN_ID>` line. These artifacts remain valid even when a later
unrelated workflow step fails; record `run.status` as evidence. A run whose
`run.status` is `failure` or `cancelled` and which lacks either valid artifact
routes to `NEEDS_HUMAN(resume_stage=LEARN_PENDING)`, never indefinite pending.
An adopted nonterminal run without a settled artifact records `next_check_at`
and a bounded `execution_deadline`; expiry likewise routes to that human state
with run ID, current `run.status`, and bounded diagnostics. Before resuming,
recheck status and artifacts: terminal runs or valid artifacts follow normal
completion. Every other return to `LEARN_PENDING`, including runner repair or
an explicitly extended wait, requires fresh `next_check_at` and a new bounded
`execution_deadline`. Human cancellation without a valid artifact uses the
supersession path. The master never cancels automatically. Only explicit human approval authorizes a same-key retry. Multiple exact-input
runs require every earlier attempt to have `run.status` of `failure` or
`cancelled` and be recorded as superseded, with the latest human-authorized
attempt adopted; all other multiple matches are ambiguous and stop recovery.
Never blindly retry. The `NO_LESSON` comment is same-run recovery evidence, not
long-term lesson content.

Deterministic recovery applies only to keyed supervised dispatches. Initial
dispatch is allowed only for a recorded `not_sent` intent or a response that
definitively rejected creation. `accepted` with zero matches remains
`LEARN_PENDING` with `next_check_at` until `dispatch_deadline`, then becomes
`NEEDS_HUMAN(resume_stage=LEARN_PENDING)`. Timeout/unknown dispatch plus zero
matches is `UNKNOWN` and immediately follows that human path. Neither case
proves non-creation or permits redispatch; only independent human-verified
non-creation evidence may record `rejected` plus `rejection_evidence` and
resume `LEARN_PENDING`. The approved same-key retry after `run.status` is
`failure` or `cancelled` above is a separate path. Manual unkeyed unknown outcomes are operator-managed by
ticket/time/run identity, jobs/logs, or the date/ticket/slug lesson path as
applicable. Manual `NO_LESSON` is logs-only, has no keyed `DONE` guarantee, and
must not be automatically redispatched. See `skills/lessons.md` for the
artifact contract and the `homelab-tickets` operator skill for dispatch
recovery and recall.

## Runner

The actions runner that executes these workflows is deployed on the NAS via
doco-cd as part of the forgejo stack: `infrastructure/synology/forgejo/`
(one compose project — the runner and its job containers share the stack
network, where the forgejo service carries the `nas.homelab.internal` alias;
same-host docker clients cannot use the LAN hairpin/fake-ip path). The live
`register` flow never completed on the NAS, so the pre-registered runner
identity (`FORGEJO_RUNNER_UUID`/`FORGEJO_RUNNER_TOKEN`) lives in
`forgejo-runner.sops.env` (age key: doco-cd's NAS-side `sops_token`); the
compose command writes `/data/.runner` from it on every start — git is the
source of truth. If Forgejo's DB is rebuilt, re-register a runner and update
the sops file. NAS HTTP and the Docker socket's host-control privilege
remain explicit accepted risks; a read-only socket mount is not isolation.

The container explicitly runs as root for NAS socket/data access; only trusted,
operator-authored workflows belong on it. The Forgejo MCP allowlist permits
ticket writes and repository reads, not workflow changes or dispatch, despite
the shared PAT's repository-write scope for the manual lessons workflow.

## Access paths

- **Canonical: `https://git.noirprime.com`** — TLS terminates at the internal
  gateway (`networking-system/forgejo-proxy`: selectorless Service + static
  EndpointSlice to `10.10.0.100:9003`); the gateway→NAS hop stays plain HTTP
  on wired VLAN 100. Cluster consumers (webhook-relay, mcp-forgejo) and the
  homepage widget use this name; DNS comes from external-dns on the route.
- **Fallback/direct: `http://nas.homelab.internal:9003`** — always served by
  the NAS itself; use when the gateway/cluster is down. NAS-side flows
  (runner via compose network alias, doco-cd, lessons) stay on it regardless.
- SSH clones: `SSH_DOMAIN=nas.homelab.internal` (gateway has no :9004).
- **OIDC**: authentik provider/application are GitOps
  (`authentik/app/blueprints/oidc/forgejo.yaml`); the Forgejo-side auth
  source is created once by `oidc-auth-source.sh` (no REST API exists for
  auth sources). Requires ROOT_URL canonical first. Local admin account stays
  as break-glass.
