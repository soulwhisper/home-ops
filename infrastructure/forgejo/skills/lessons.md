# Lessons learnt format

Distilled memory, written by whoever fixed the ticket (agent or human), at
ticket close. Lives in `learnings/` — plain markdown, half a page max, only
what would make the next incident faster.

## File

`learnings/YYYY-MM-DD-<slug>.md`

```markdown
---
ticket: 42
pr: soulwhisper/home-ops#3999
root_cause_class: config-drift | capacity | upstream-bug | secret-rotation | other
confidence: verified | suspected
---

# <one-line lesson>

**Symptom**: what fired, in one line.
**Root cause**: the actual mechanism, not the surface error.
**Fix**: what changed (PR link), in one line.
**Faster next time**: the single thing that would have cut MTTR — a query, a
log line, a panel, a runbook step.
```

## Rules

- One lesson per distinct root cause. A repeat incident gets a comment on the
  existing lesson, not a new file.
- No secrets, no credentials, no customer data. Hostnames and namespaces are
  fine — this repo never leaves the LAN.
- If the fix was "revert", the lesson says why it was wrong the first time.
