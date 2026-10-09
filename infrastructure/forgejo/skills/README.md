# homelab-tickets conventions

The ai-ops work queue. Detectors file tickets here; the operator (with the
fixer agent) works them. This file is the law — synced from
`home-ops/infrastructure/forgejo/skills/`, edit there.

## Ticket anatomy

- **Title**: `[SEV] <finding title>`.
- **Body**: source, `aggregation_key`, fingerprint, subject
  (kind/name/namespace), observation and fire/resolve timestamps, and enrichment.
  The consumer's leading incident marker hashes source + `aggregation_key`;
  this pair, not a title or fingerprint alone, identifies the incident.
- **Comments**: new observations and resolutions extend the incident timeline.
  Exact event replays are suppressed; only a new failure can reopen a closed
  ticket. Resolution is evidence, never automatic permission to close.
  The operator may add `flap` when the timeline shows repeated transitions.

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
