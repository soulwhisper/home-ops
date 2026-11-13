# Hermes Agent (archived)

Retired from the cluster because the homelab runs exactly one Hermes: the native
instance on `nix-ops` (`nix-config` → `hermes-agent`, dashboard on
`10.10.0.200:9119`). Two gateways meant two Feishu websocket consumers, two cron
tickers and two copies of memory, and the cluster copy held the authoritative
`/opt/data`.

## What moved with it

- Authentik forward-auth blueprint →
  `.archived/kubernetes/security/authentik/blueprints/forward/hermes-agent.yaml`
- its entry in `kubernetes/apps/servitor-apps/kustomization.yaml`
- the `dependsOn: hermes-agent` in `open-webui/ks.yaml`
- its provider binding in `blueprints/core/outpost-proxy.yaml`

## Data warning — read before the prune lands

The app mounted the kopiur-backed PVC `hermes-agent` (5 Gi, `ceph-block`) at
`/opt/data`: sessions, cron state, skills, memories. That PVC and its
`SnapshotPolicy` come from `components/kopiur/backup`, so removing the app from
git prunes them. Either keep the volume:

```sh
kubectl -n servitor-apps annotate pvc hermes-agent \
  kustomize.toolkit.fluxcd.io/prune=disabled --overwrite
```

Use the Flux annotation, not Helm's `helm.sh/resource-policy: keep`: this PVC is
created by the app's Kustomization (through `components/kopiur/backup`), and
kustomize-controller does not read Helm's annotation.

or copy `/opt/data` out (or snapshot it) before the Kustomization reconciles.
Kopiur snapshots already written to S3 survive the prune.

## Restore

Move the folder to `kubernetes/apps/servitor-apps/hermes-agent` (the archived
`ks.yaml` already points at that path), then re-add `- ./hermes-agent/ks.yaml` to
`kubernetes/apps/servitor-apps/kustomization.yaml`, put back the `open-webui`
`dependsOn` if ordering still matters, and restore **both** Authentik changes
(file-list entry and outpost provider) or the dashboard comes back unserved.
The Feishu app credentials are in the `hermes-agent` 1Password item — note that
restoring this app makes a second websocket consumer of the same bot.

## Renovate configuration for restore

`.renovate/autoMerge.json5` lost one entry when this app was archived: the image
was in the "Kubernetes, Talos, and sensitive app updates require human review"
rule (`matchPackageNames`), so a Hermes bump could never auto-merge. Renovate
ignores `.archived/**`, so re-add it with the app:

```json5
        "ghcr.io/soulwhisper/hermes-agent",
```

Without it the image falls back to the user-apps automerge rule for patch and
minor bumps — the opposite of what a hand-tracked agent build wants.
