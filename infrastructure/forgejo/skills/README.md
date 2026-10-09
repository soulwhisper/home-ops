# homelab-tickets conventions

The ai-ops work queue. Detectors file tickets here; the operator (with the
fixer agent) works them. This file is the law — synced from
`home-ops/infrastructure/forgejo/skills/`, edit there.

## Ticket anatomy

- **Title**: `[SEV] <finding title>`.
- **Body**: source, `aggregation_key`, fingerprint, subject
  (kind/name/namespace), observation and fire/resolve timestamps, and enrichment.
  The consumer's leading incident marker hashes source + `aggregation_key` +
  fingerprint: one ticket per alert instance (Prometheus findings use the
  alert name as `aggregation_key`; the fingerprint separates pods/namespaces).
- **Comments**: state transitions (fire, resolve, re-fire) extend the incident
  timeline. Re-notifications of an unchanged state are suppressed; only a new
  failure can reopen a closed ticket. Resolution is evidence, never automatic
  permission to close. The operator may add `flap` when the timeline shows
  repeated transitions.
- **Holmes investigation**: one automated comment on create/reopen (root
  cause, evidence, proposed fix, verification). A hypothesis to confirm, not a
  verdict; absent if Holmes timed out.

## Lifecycle

1. `open` — inbox. Nobody owns it yet.
2. **Claim** — comment `taking` (and assign yourself) before starting work.
   Merge historical duplicates or distinct keys with the same root cause:
   close the losers with a link to the survivor; do not edit consumer markers.
3. **Fix** — change goes to `home-ops` on GitHub as a PR. Public PRs stay
   terse: what + why-in-one-line + ticket number. No incident prose, no
   internal detail — context lives here, not there.
4. **Verify** — prove it per `skills/acceptance.md` for the ticket's class.
5. `closed` — one closing comment: PR link + the verification evidence.

## Fixer rules

- The human merges. Agents propose, never merge.
- Nothing mutates the cluster outside flux. The fix is always a git change.
- Blast radius beats elegance: prefer the boring, reversible fix.
