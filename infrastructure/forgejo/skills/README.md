# homelab-tickets conventions

The ai-ops work queue. Detectors file tickets here; the operator (with the
fixer agent) works them. This file is the law — synced from
`home-ops/infrastructure/forgejo/skills/`, edit there.

## Ticket anatomy

- **Title**: `[SEV] <alertname or check> — <subject> (<namespace>)`
- **Body, first block**: `aggregation_key`, fingerprint, subject
  (kind/name/namespace), first-fired and last-fired timestamps. The
  `aggregation_key` is the dedupe key — search it before treating anything as
  new.
- **Comments**: repeat fires and fire→resolve cycles land as comments on the
  same ticket (the ticket is the incident timeline). A flapping ticket gets
  the `flap` label.

## Lifecycle

1. `open` — inbox. Nobody owns it yet.
2. **Claim** — comment `taking` (and assign yourself) before starting work.
   Merge obvious duplicates (same `aggregation_key` or same root cause):
   close the losers with a link to the survivor.
3. **Fix** — change goes to `home-ops` on GitHub as a PR. Public PRs stay
   terse: what + why-in-one-line + ticket number. No incident prose, no
   internal detail — context lives here, not there.
4. **Verify** — prove it per `skills/acceptance.md` for the ticket's class.
5. `closed` — one closing comment: PR link + the verification evidence.

## Fixer rules

- The human merges. Agents propose, never merge.
- Nothing mutates the cluster outside flux. The fix is always a git change.
- Blast radius beats elegance: prefer the boring, reversible fix.
