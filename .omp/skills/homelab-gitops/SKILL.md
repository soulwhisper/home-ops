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

Talos nodes are immutable; mutate them by patching machine config sources
under `infrastructure/talos/`, then use the repo's apply recipe. Files under
`clusterconfig/` are GENERATED output — edit sources/patches, regenerate,
never hand-edit the output.

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
   green. When the user says the PR is merged: switch to main, pull, clean
   up stale local branches/state, reconcile the cluster (flux sync), check
   post-merge status (pods, kustomizations, health warnings), then close
   with a summary report and suggested post-fixes if anything is off.
