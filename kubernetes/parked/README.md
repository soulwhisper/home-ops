# Parked applications

`kubernetes/parked/` holds definitions that are intentionally **not deployed**.
Flux never reconciles this tree: it sits outside the `cluster-apps` path
(`kubernetes/apps`), so parked manifests cannot be deployed by accident.

The only lifecycle difference from `.archived/` is intent:

- **parked** — may return. Definitions are kept complete and resumable; the
  application's data is **not** preserved. Restoring means moving the
  directory back under `kubernetes/apps/<namespace>/` and re-adding its
  `ks.yaml` to the namespace index, accepting a fresh/empty data set (or an
  explicit backup restore).
- **`.archived/`** — historical reference only. Definitions are not guaranteed
  to be deployable and are not maintained.

Both methods discard workload data; parked is not a backup mechanism. Removing
a parked application from the active indexes deletes its workloads and PVCs;
CNPG databases/roles and leftover kopiur Snapshot objects still require the
manual post-merge cleanup. NAS-hosted files are left untouched by the
cluster-side deletion, but their PV/PVC bindings are gone.

Each parked application keeps its `ks.yaml`. Parked Authentik blueprints
mirror the active tree under
`kubernetes/parked/security-system/authentik/blueprints/{forward,oidc}/`, so
they can be copied back with the rest of the configuration. The parked tree
has no Kustomization index of its own.

`spec.path` values in parked `ks.yaml` files are intentionally left at their
canonical `kubernetes/apps/...` location. Flux never renders this tree, so
those paths are inert; parking and resuming stay pure directory moves with no
path edits.
