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

## Sync

This repo is the source of truth; after edits, push `skills/` and `workflows/`
into the tickets repo by hand (clone → rsync both dirs → commit → push,
authenticated with `forgejo.pat_tickets`). The tickets repo holds no other
tracked content.


## Runner

The actions runner that executes these workflows is deployed on the NAS via
doco-cd: `infrastructure/synology/forgejo-runner/`. Registration token and
secrets live in 1Password (`forgejo` item), injected NAS-side — never
committed.
