---
name: homelab-gitops
description: Use whenever the request involves the Kubernetes cluster, Talos nodes, kubectl, flux, kustomize, helm, secrets/sops, or any K8s resource (pods, deployments, services, ingresses, CRDs) — or the recorded infrastructure under infrastructure/ (talos, synology, switch, dnscontrol). Trigger for casual mentions like "deploy this", "check the cluster", "scale up", "what's wrong with the pod", "add an env var/secret", or any reference to a node, a kubeconfig context, a flux kustomization, or a helm release.
---

# Homelab GitOps (home-ops)

Single-cluster Talos homelab, solo operator. Blast radius matters even at
small scale.

## Infrastructure truth

`infrastructure/` holds the recorded/gitops-managed state of non-cluster
infra (talos machine configs, synology, switch, dnscontrol). Treat those
files as the source of truth for how the infra is INTENDED to look:

- Read them as reference before advising on anything infra-adjacent —
  don't reconstruct topology or addressing from cluster state alone.
- If live state or another config contradicts what's recorded there,
  SURFACE the discrepancy to the user explicitly. Never silently pick one
  side; the file is the intent, the drift is the story.

## Blast radius proportionality

When weighing blast-radius or redundancy/replica concerns, FIRST check the
recorded physical design (`infrastructure/switch/README.md` topology,
node count in `infrastructure/talos/`). As recorded: single WAN (PPPoE),
single router, single core switch, single access switch, single NAS — the
cluster's nodes share all of them.

Rule: if a proposed mitigation guards a failure domain that the shared
physical/network layer collapses anyway (a switch/router/WAN outage kills
every replica, however spread), do NOT present it as important or give it
weight in the risk assessment. Note it as a known gap, suggest improving
the underlying redundancy later, and move on. Reserve real weight for
failure domains that are actually independent — e.g. node-level failures,
where the 3 nodes genuinely are 3 domains.

## Heavy-impact operations — stop and ask first

Before anything destructive/heavy-impact/service-breaking — node reboots,
mass pod deletes, force-deletes of stateful workloads, etcd-affecting
actions, storage-side deletions — STOP:

1. State the risk plainly: what breaks, worst case, recovery path
   (including whether recovery might need physical/AMT access).
2. Ask the user to confirm or assist — use omp's `ask` tool; do not bury
   it in prose. "Continue?" after a risk summary is the minimum.
3. If a remote command wedges mid-execution (e.g. graceful reboot stuck on
   wedged containerd), tell the user immediately that physical/AMT
   intervention may become necessary — don't keep silently retrying.

2026-09-24 proof: the recovery reboot hung on wedged containerd; the user
had to AMT-cycle the nodes by hand. The agent should have flagged that
risk BEFORE issuing the reboot, not after.

## Discover before acting — don't assume, read the repo

Cluster facts, versions, and tooling change. Ground every session in the
checked-in sources instead of memory:

```bash
# Toolchain + env (KUBECONFIG, TALOSCONFIG, flux namespace, rook namespaces,
# talosctl pin, ...):
cat .mise.toml

# Talos / Kubernetes target versions and schematic ids:
cat infrastructure/talos/version.yaml

# Available operational recipes (sync/render/apply/snapshot/reboot/...):
just --list

# Installed kubectl plugins (rook_ceph, browse-pvc, stern, ...):
kubectl plugin list
```

Rules that follow from the configs:

- Honor the env from `.mise.toml` (run from repo root so mise applies it);
  flux's namespace is `FLUX_SYSTEM_NAMESPACE`, not an assumed default.
- `talosctl` must match the cluster's Talos major.minor — the pin in
  `.mise.toml` / `version.yaml` is the source of truth.
- kubectl plugins are managed by krew; if a `just` recipe calls a plugin
  (`kubectl <something>` with a dash/underscore name), confirm it in
  `kubectl plugin list` before debugging anything else. Manage plugins with
  the `krew` binary (`krew list|install|upgrade`).

## Always-first commands

```bash
# Confirm which cluster you're about to touch — single most common mistake.
kubectl config current-context

kubectl get nodes -o wide
kubectl get pods -A | grep -vE 'Running|Completed'   # only the not-OK ones
kubectl -n "$FLUX_SYSTEM_NAMESPACE" get kustomizations
```

If you don't see what you expected — wrong context or flux is mid-reconcile.
Stop before any further command.

## GitOps model

Everything under `kubernetes/` is Flux-reconciled; cluster state follows git.
Orient with the repo, not assumptions:

- `kubernetes/apps/<namespace>/<app>/` — HelmRelease + OCIRepository; larger
  apps split into subdirs (operator/cluster/drivers pattern).
- `kubernetes/components/`, `kubernetes/bootstrap/`.
- Secrets are SOPS-encrypted → `secrets-sops` skill.

Rules:

- Direct `kubectl apply`/`edit` against flux-managed objects is drift; flux
  reverts it. For a quick local test use the repo's render/apply recipes
  (`just --list` → the `render-ks`/`apply-ks` pair, which apply with flux's
  field-manager); for permanence edit git, then force a sync with the
  `sync-*` recipes.
- Helm values belong in the HelmRelease in git, never `helm upgrade` by hand.

## Comments and removal hygiene

Code and manifest comments describe the current invariant or the reason for
the current code. They are not a changelog.

- When fixing or updating, write a short plain-text reason for the fix.
  Do not include dates, incident/commit references, security-sensitive
  details (topology, credential leaks, design failures, third-party bug
  history), or hints that the change aligns with a person, team, or
  external change.
- Third-party configuration comments split on control:
  1. If we control the config, do not leave a comment implying we follow
     the third party's rule. We choose the shape, and the comment will
     drift.
  2. If we cannot control it, keep a short comment recording the constraint
     so a future change can align with it.
- When removing something, remove it cleanly. Do not leave a tombstone
  comment describing what was removed, why it existed, or what should
  replace it later.
- Do not leave "delete once upstream fixes X" workaround notes. If a
  workaround must stay, describe the invariant it enforces now.
- When touching surrounding code, delete comments that only narrate
  history.

## Archiving an application

`kubernetes/` is the only reconciled tree. Archive with `git mv`; do not delete
the manifests.

1. Move `kubernetes/apps/<namespace>/<app-path>` to
   `.archived/kubernetes/<namespace-without-apps-or-system>/<app-path>`,
   preserving grouping directories (for example
   `servitor-apps/mcp/smarthome` → `.archived/kubernetes/servitor/mcp/smarthome`,
   `monitoring-system/headlamp` → `.archived/kubernetes/monitoring/headlamp`).
2. Remove the app's `ks.yaml` from the nearest `kustomization.yaml` that lists
   it (for `servitor-apps/mcp/<app>` that is
   `kubernetes/apps/servitor-apps/mcp/kustomization.yaml`, not the namespace
   root). If a replacement lands in the same change, add it there.
3. Keep every archived `ks.yaml` byte-identical, including `spec.path`. The
   path stays at its canonical `kubernetes/apps/...` location and is inert
   because Flux never reads `.archived`.
4. Move the app's Authentik blueprint from
   `kubernetes/apps/security-system/authentik/app/blueprints/{core,forward,oidc}/<app>.yaml`
   into the archived app directory, mirroring the blueprint subdirectory. Remove
   it from the authentik `kustomization.yaml` and from the HelmRelease
   `blueprints.secrets` list when mounted. For forward-auth apps, also remove
   the provider from `blueprints/core/outpost-proxy.yaml`.
5. Delete active-only assets the app referenced (for example Homepage icons and
   their `kustomization.yaml` entries).
6. Add one row to `.archived/README.md`: path, what it is, and why it is
   archived. Update the counts and namespace rows in
   `docs/application/catalog.md` and `docs/infrastructure/kubernetes.md`.
7. Remove the app from the docs that describe the active architecture
   (`docs/application/*`, `docs/decisions/*`, resource baselines) and from any
   active `ks.yaml` `dependsOn` entry.
8. Do not add an ignore file, kubeconform exclusion, or Renovate rule for the
   archived path: `.archived/` sits outside `kubernetes/`, so Flux, flate and
   the `^kubernetes/` hooks never see it. When an archived app is replaced by a
   native resource, add that resource under `kubernetes/apps/` in the same
   change.
9. Verify with `flate test all --base main`, yamllint/kubeconform on the
   changed manifests, and a server-side dry-run for cluster-scoped resources.

## Storage

Discover the actual layout instead of assuming names:

```bash
kubectl get sc                                    # storage classes + default
kubectl -n <storage-ns> get cephcluster,cephblockpool,cephfilesystem
```

- Find the rook/ceph namespaces from `.mise.toml` (`ROOK_*_NAMESPACE`) or
  `ls kubernetes/apps/`.
- CSI driver name prefixes are baked into PVs, StorageClasses, and
  VolumeSnapshotClasses (all immutable fields). Never rename a driver; check
  the prefix with `kubectl get csidrivers` before touching storage config.
- A size=1 / scratch-class pool is for rewarmable data only — verify a
  pool's replication before pointing anything durable at it.
- Ceph CLI: check whether the toolbox is enabled in the cluster HelmRelease;
  if not, use the rook-ceph kubectl plugin (`kubectl rook-ceph ceph status`,
  `... ceph osd df`, `... radosgw-admin ...`), which reads the
  `ROOK_*_NAMESPACE` env vars.
- Backups/snapshots: look for the in-repo mechanism
  (`kubectl get snapshotpolicies -A`, snapshot recipes in `just --list`)
  before inventing one.

## Reading resources

```bash
kubectl get <kind> -n <ns>
kubectl describe <kind>/<name> -n <ns>
kubectl logs -n <ns> <pod> [-c <container>] [-f] [--previous]
kubectl get events -n <ns> --sort-by=.lastTimestamp | tail -20
```

For a workload that's misbehaving, the canonical triage order is:
`describe pod` (events) → `logs --previous` (crash before restart) →
`logs -f` (current). Check restarts (`restartCount`, `lastState`) before
blaming resources — OOMKilled and app-level exits need different fixes.

For VictoriaMetrics/VictoriaLogs/VictoriaTraces label discovery and bounded
evidence queries, use `skill://victoria-reports` when installed; it carries the
read-only endpoints, human-facing label vocabulary, PromQL/LogsQL/trace
recipes, and the dashboard contract.

## Victoria stack evidence extraction

If `skill://victoria-reports` is available, it is the source of truth for
Victoria labels and query recipes. For label-only extraction, do **not** render
its dashboard and do not create a `temp/` HTML file:

1. Read the skill's label vocabulary and required-coverage sections. Use the
   exact label keys from there; do not copy or re-derive them here.
2. Confirm the context and port-forward the needed backends. Keep every query
   bounded with `start`/`end`, `_time`, and a `limit`.
3. Return the discovered labels, values, and aggregates in chat as compact JSON
   or a table. Include the exact query and timestamp.

Set the endpoints, open the forwards, and wait for readiness before any probe:

```bash
V=http://127.0.0.1:8428
L=http://127.0.0.1:9428
T=http://127.0.0.1:10428
START=$(date -u -d '1 hour ago' +%s)
END=$(date -u +%s)
pids=()
cleanup() { kill "${pids[@]}" 2>/dev/null || true; }
trap cleanup EXIT

kubectl -n monitoring-system port-forward svc/vmsingle-victoria-metrics-cluster 8428:8428 &
pids+=($!)
kubectl -n monitoring-system port-forward svc/victoria-logs-server 9428:9428 &
pids+=($!)
kubectl -n monitoring-system port-forward svc/victoria-traces 10428:10428 &
pids+=($!)

wait_ready() {
  for _ in $(seq 1 20); do
    curl -fsS "$1" >/dev/null 2>&1 && return 0
    sleep 1
  done
  return 1
}
wait_ready "$V/api/v1/query?query=1" || echo "VMSingle not ready" >&2
wait_ready "$L/select/logsql/query?query=_time:1m&limit=1" || echo "VictoriaLogs not ready" >&2
wait_ready "$T/select/jaeger/api/services" || echo "VictoriaTraces not ready" >&2
```

Minimal discovery probes, after the readiness checks:

```bash
# metrics labels and matching series
curl -fsS --get "$V/api/v1/labels" \
  --data-urlencode "start=$START" --data-urlencode "end=$END"
curl -fsS --get "$V/api/v1/series" \
  --data-urlencode 'match[]=gotk_resource_info' \
  --data-urlencode "start=$START" --data-urlencode "end=$END" \
  --data-urlencode 'limit=200'

# log field names/values, bounded
curl -fsS --get "$L/select/logsql/field_names" \
  --data-urlencode 'query=_time:1h' --data-urlencode 'limit=200'
curl -fsS --get "$L/select/logsql/stream_field_values" \
  --data-urlencode 'query=_time:1h' \
  --data-urlencode 'field=kubernetes.pod_namespace' --data-urlencode 'limit=50'

# trace services
curl -fsS "$T/select/jaeger/api/services"
```

Use the dashboard/template only when the user explicitly asks for a visual
artifact. Label extraction, incident triage, and evidence gathering end in the
chat response, not in an HTML file.

### Missing-skill fallback

If `skill://victoria-reports` is absent, do not fail the task and do not invent
a label vocabulary. Reuse the bounded setup and probes above, report
`查询失败` for any backend that never became ready, and return the observed
labels/values in chat with their timestamps. State that the dedicated skill was
unavailable; still do not create an HTML artifact.

## Mutating safely

Every mutation must go through diff → confirm → apply → verify, with the
rollback named BEFORE applying.

```bash
# Render what flux would apply, then diff it:
<render recipe> | kubectl diff -f -
<apply recipe>
kubectl rollout status deploy/<name> -n <ns>
```

Diff/preview commands by target (dry-run before any apply):

| Target | Preview |
|--------|---------|
| kubectl manifest | `kubectl diff -f <file>` or `kustomize build … \| kubectl diff -f -` |
| Helm release | `helm diff upgrade <release> <chart> -n <ns> -f values.yaml` |
| Talos machine config | `talosctl -n <node> diff` |
| NixOS / nix-darwin | `nixos-rebuild build` then `nvd diff /run/current-system result` (fallback: `nix store diff-closures`) |

Rules (from the retired infra-operator agent — they were right):

- State the rollback in one sentence before running the mutation
  (`kubectl rollout undo …`, `helm rollback …`, `talosctl rollback`,
  re-apply prior git SHA). No clean rollback (e.g. CRD data migration) →
  say so loudly.
- Never push to a host/node you weren't asked to touch; no symmetry
  rebuilds.
- Don't declare done at exit 0: `rollout status`, `talosctl health`,
  actually `curl` exposed services, `journalctl -u <unit>` for activations.

Mutating commands are gated by omp's `tools.approval` settings.
The user will be prompted; don't try to suppress that.

## Talos-specific

Talos nodes are immutable. Edit machine config sources under
`infrastructure/talos/`, regenerate derived output, and never hand-edit
`clusterconfig/`. For live machine-config changes, use
`talosctl patch machineconfig` with the smallest valid YAML merge for the
changed document/fields — never a full `talosctl apply-config` replacement.

- Always run `talosctl patch machineconfig --dry-run --nodes <node>
  --patch-file <patch.yaml>` first, with an explicit patch payload, and patch
  one node at a time; concurrent applies contend for the node apply lock.
- For `UnattendedInstallConfig`, patch that document's `installer.image` while
  preserving required sibling fields (`provisioning.diskSelector.match`); do
  not use the legacy `.machine.install` path.

```bash
talosctl -n <node> version
talosctl -n <node> dmesg | tail -50
talosctl -n <node> health
talosctl -n <node> diff        # against the new machine config
```

- Read `.justfiles/talos.just` before bring-up work — it records hard-won
  caveats (network pre-config requirements, bootstrap ordering).
- Never reset a node without naming the node explicitly in the confirmation.
  There is no undo.

## Deleting things

Hard floor: do not delete a namespace, PVC, StatefulSet, or CRD without an
explicit user confirmation that names the resource (not just "yes, the
thing"). Side effects:

- Namespace deletion: cascades to every resource and lingers in `Terminating`
  if a finalizer is stuck — that's a separate triage path
  (`kubectl get … -o json | jq '.metadata.finalizers'`, then surgical
  patch).
- PVC deletion: check the StorageClass `reclaimPolicy` first — with `Delete`
  it *deletes the volume*.
- StatefulSet deletion: pods go, PVCs may stay or may not (cascade policy).

## Read-only access

Kubeconfig/talosconfig material (in-repo `clusterconfig/` and `~/`) contains
CA material and client certs — treat as sensitive. omp's `tools.approval`
settings may restrict read access; do not work around this. Regeneration
from the password manager is covered by the repo's restore recipe.

## Secrets (flux sops)

Model: secrets live in git as `*.sops.yaml`, encrypted with the cluster's
age key via sops; flux decrypts in-cluster at reconcile time.

Iron rules:

1. **Never echo, log, paste, or `cat` a decrypted secret** — not in chat,
   not in diffs, not "for context". `kubectl get secret -o yaml` output is
   base64 ciphertext-adjacent; treat it as the secret.
2. Edit encrypted files with `sops <file>` only — never create plaintext
   secret manifests "temporarily".
3. A diff on a `*.sops.yaml` must show only re-encrypted ciphertext. If
   plaintext fields appear, stop and treat it as a leak.
4. Rotating: `sops` edit → commit → flux reconcile (`sync-ks` recipe) →
   restart consumers that cached the value. If a secret is suspected
   leaked, rotate at the source FIRST, then update the repo.

## Hand-offs

- YAML-only change in git, no live-cluster impact yet → ordinary code edit;
  flux picks it up (or force with a sync recipe).
- Secrets/SOPS → see Secrets (flux sops) above; pre-commit/lint/review →
  `code-review` skill.
- "I'm scared this is going to break prod" → stop and walk the Mutating
  safely checklist explicitly with the user before touching anything.

## Session workflow rules

Standing agreements with the operator. They override the default urge to
edit.

1. **Eval means eval.** When the user asks to evaluate/check/compare
   something (a config, an upstream repo, a cluster state): investigate,
   analyze, deliver a report. NO edits — not even "while you're in there"
   fixes. Findings and recommendations only.
2. **Feature work is two-phase.** For every feature/change request: first
   run the eval phase (investigate + propose, no edits) and explicitly ask
   to continue. Only after the user's go-ahead: implement on a branch and
   open a PR.
3. **Post-PR loop.** After the PR is pushed: watch CI, fix CI errors until
   green. When the user says the PR is merged: switch to main, pull, clean up
   stale local branches/state, run `just reconcile` once, then wait read-only.
   `just reconcile` is exactly `flux reconcile kustomization gitops-system
   --with-source`: it pulls the new Git revision and applies the top-level
   Kustomization only. Child Kustomizations and HelmReleases then reconcile
   on their own interval and `dependsOn` order. Do not force-reconcile
   individual child Kustomizations or HelmReleases — that races their
   dependencies and can abort.
   First read the PR's merge commit SHA and bind the gate to that exact
   target. Wait until every affected child Kustomization has applied that
   Git revision and is `Ready=True` (record its condition reason), and each
   affected HelmRelease is `Ready=True` with `status.observedGeneration`
   caught up to `metadata.generation`. An applied revision alone is not
   health; a stale `Ready` without the merged generation is not convergence.
   Do not report the intermediate state (old revision, dependency-pending,
   rollout in progress) as the post-merge result. Only after convergence,
   close with a summary and post-fixes.
   Use a bounded read-only check. After the bound, record the target SHA,
   applied revisions, and `next_check_at` and return `PENDING_RECONCILE`;
   never poll indefinitely. Report failure only on a completed error or after
   the bound expires, with the exact failing resource, condition reason, and
   a concrete fix. Never report an intermediate state as success.
