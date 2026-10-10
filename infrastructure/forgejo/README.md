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
lookup and replay suppression. Human merge, verification, closure, and manual
lessons dispatch remain required; no auto-fixer or complete API audit history
is implied.

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
prefixes) and `LLM_API_KEY` (`llm-api.agentgateway_api_auth`).

## Runner

The actions runner that executes these workflows is deployed on the NAS via
doco-cd: `infrastructure/synology/forgejo-runner/`. Registration token and
secrets live in 1Password (`forgejo` item), injected NAS-side — never
committed. Its working directory is `/data`; successful registration persists
`/data/.runner`, which gates re-registration. No nonexistent `config.yml` is
passed to the runner. NAS HTTP and the Docker socket's host-control privilege
remain explicit accepted risks; a read-only socket mount is not isolation.

The container explicitly runs as root for NAS socket/data access; only trusted,
operator-authored workflows belong on it. The Forgejo MCP allowlist permits
ticket writes and repository reads, not workflow changes or dispatch, despite
the shared PAT's repository-write scope for the manual lessons workflow.
