---
name: homelab-tickets
description: Use whenever the request involves ai-ops tickets — checking, triaging or working Forgejo homelab-tickets issues, fixing/verifying/closing an incident, writing a lesson (learnings/), or recalling/retaining incident memory (hindsight aiops bank). Trigger for "check tickets", "work the ticket queue", "what's open in homelab-tickets", "close #N", "write the lesson", "did we see this before".
---

# homelab-tickets: check → fix → verify → learn → remember

The ai-ops work queue lives in Forgejo `soulwhisper/homelab-tickets` on
`http://nas.homelab.internal:9003` (intranet-only, plain HTTP, public repo —
both accepted). The **law** for tickets is `infrastructure/forgejo/skills/` in
this repo — read `README.md` (anatomy, lifecycle) and `acceptance.md`
(per-class verification bar) locally before working a ticket. The tickets
repo holds a synced copy (`just forgejo sync`) for its own workflows; if the
two differ, this repo is authoritative and the copy is stale. This skill is
the operator procedure; on conflict, the law wins.

Pair with `homelab-gitops` for every cluster read/change.

## Pipeline facts (don't rediscover)

- Alertmanager → Robusta → `webhook-relay` route `robusta-tickets`
  (MEDIUM/HIGH; `warning` alerts arrive as HIGH via `custom_severity_map`) →
  serialized consumer
  (`kubernetes/apps/monitoring-system/webhook-relay/app/ticket_consumer.py`).
- **One issue per alert + affected workload**: first body line is
  `<!-- aiops-incident:<sha256(source, alertname, scope)> -->`, where scope is
  the namespace/workload/node/container labels with Deployment pod hashes
  stripped. A rollout's new pods and a rule-error storm across many rule
  groups land on the same ticket. Never edit or remove the marker.
- Only Alertmanager-sourced (`PROMETHEUS`) findings are ticketed; Robusta's
  builtin OOM/CrashLoop/ImagePull/Evicted findings go to Feishu only.
- **Comments** are per-instance state transitions (fire / resolve /
  re-fire). 12h re-notifications of the same state are suppressed. A new
  failure reopens a closed issue; a resolution never closes one.
- **Holmes** posts a `**Holmes investigation**` comment (marker
  `<!-- aiops-holmes -->`) on create, and on reopen at most once per 6h. It is
  a hypothesis: confirm its evidence yourself; it may be absent if Holmes
  timed out.
- Labels in the repo: none by default. Only add `flap` (repeated transitions)
  — don't invent a taxonomy.

## 1. Check the queue

Reads need no token (public repo):

```bash
F=http://nas.homelab.internal:9003/api/v1/repos/soulwhisper/homelab-tickets
# paginate: Forgejo caps pages at 50; loop until a short page
for p in $(seq 1 100); do
  page=$(curl -fsS "$F/issues?state=open&type=issues&limit=50&page=$p")
  echo "$page" | jq -r '.[] | [.number, .updated_at[:16], .comments, .title] | @tsv'
  [ "$(echo "$page" | jq length)" -lt 50 ] && break
done
curl -fsS "$F/issues/<N>" | jq -r .body                 # finding + markers
for p in $(seq 1 100); do                                # full comment timeline
  page=$(curl -fsS "$F/issues/<N>/comments?limit=50&page=$p")
  echo "$page" | jq -r '.[] | .created_at[:16] + "\n" + .body + "\n---"'
  [ "$(echo "$page" | jq length)" -lt 50 ] && break
done
```

Triage order: HIGH before MEDIUM, then oldest. For each, decide in one line:
real / noise (rule threshold wrong) / duplicate root cause of another open
ticket. A burst of tickets in one window (e.g. many controllers restarting) is
usually **one** root cause — work the earliest, link the rest.

## 2. Claim

Writes need `pat_tickets` (never echo it):

```bash
export FORGEJO_TOKEN="$(op item get forgejo --fields pat_tickets --reveal)"
fj() { curl -fsS -H "Authorization: token $FORGEJO_TOKEN" -H 'Content-Type: application/json' "$@"; }
fj -X POST "$F/issues/<N>/comments" -d '{"body":"taking"}'
```

Duplicates: comment `duplicate of #<survivor>` and close the loser
(`fj -X PATCH "$F/issues/<N>" -d '{"state":"closed"}'`). Do not touch markers.

## 3. Recall before diagnosing

Ask incident memory whether this was seen before (aiops bank, isolated from
chat memory). Prefer the `hindsight-ops` MCP `reflect`/`recall` tools via
`https://api.noirprime.com/mcp/ops` when available; otherwise REST:

```bash
kubectl -n selfhosted-apps port-forward svc/hindsight 18888:8888 &
curl -fsS -X POST http://127.0.0.1:18888/v1/default/banks/aiops/memories/recall \
  -H 'Content-Type: application/json' \
  -d '{"query":"<alertname> <namespace>/<workload> <symptom>","max_tokens":2000}' | jq '.results'
```

Also grep past lessons: `curl -fsS "$F/contents/learnings" | jq -r '.[].name'`.
A 404 bank means nothing retained yet — not an error.

## 4. Diagnose and fix

- Reproduce the signal from **raw data** (VictoriaMetrics query, logs), not
  from the ticket text. Record the query; it becomes verification.
- The fix is a git change in `home-ops`, on a branch, as a GitHub PR. Public
  PR text stays terse: what + one-line why + `homelab-tickets#<N>`. Incident
  detail stays in the ticket.
- Agents propose, the human merges. No `kubectl apply/edit/delete` of
  Flux-managed objects. One-off live actions (rollout restart to clear state)
  need explicit user approval and must be recorded in the ticket.
- Comment the PR link on the ticket as soon as it exists.

## 5. Verify (after merge + reconcile)

Apply `acceptance.md` for the ticket's class. Minimum for alert tickets:

1. The raw rule expression is normal for the ticket's scope (same alert,
   namespace and workload; every instance, not just one pod).
2. A `**Event:** resolved` comment from the consumer exists (or explain why
   the alert cannot resolve yet, e.g. `for:` window).
3. Alert/kyverno classes: re-check after 24h before calling it durable.

Silence, inhibition or an empty Alertmanager result is **not** healing.

## 6. Close

One closing comment, then close:

```text
Fixed by soulwhisper/home-ops#<PR>.
Verification: <query> → <before> → <after> (<timestamp>).
Root cause: <one line>.
```

## 7. Learn (lesson file)

For a distinct root cause, dispatch the lessons workflow (writes
`learnings/YYYY-MM-DD-<slug>.md` per `skills/lessons.md`):

```bash
fj -X POST "$F/actions/workflows/lessons.yml/dispatches" -d '{"ref":"main","inputs":{"ticket":"<N>"}}'
```

Dispatch is operator-only: the Forgejo MCP allowlist deliberately excludes it
(the NAS runner is root-capable). Repeat incident of a known root cause →
comment on the existing lesson's ticket instead of a new lesson.

## 8. Remember (incident memory)

Retain one distilled entry per closed incident into the aiops bank — facts
only, no secrets, no raw log dumps:

```bash
curl -fsS -X POST http://127.0.0.1:18888/v1/default/banks/aiops/memories \
  -H 'Content-Type: application/json' -d '{"items":[{
    "content":"<alertname> on <ns>/<workload>: root cause <...>; fixed by home-ops#<PR>; verify with <query>.",
    "context":"homelab-tickets#<N>",
    "tags":["<alertname>","<namespace>","<root_cause_class>"]}]}'
```

Use the same tags as earlier entries (`list_tags` via MCP). Agents with the
MCP use `retain` with the same content.

## Don'ts

- Don't close on Holmes' word, on a silence, or before the fix reconciled.
- Don't create tickets by hand for alerts — the consumer owns intake;
  hand-made tickets lack the marker and will be duplicated.
- Don't rsync or delete `learnings/` files you did not write.
- Don't paste tokens, kubeconfig or Secret values into tickets, PRs or memory.
