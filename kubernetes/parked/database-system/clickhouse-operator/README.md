# ClickHouse operator and cluster (parked)

Parked with Langfuse. Langfuse was the only consumer, so this app has no active
dependents. See
[`../../monitoring-system/langfuse/README.md`](../../monitoring-system/langfuse/README.md)
for the full cross-app cleanup, leftovers, data notes, and unpark order.

## Contents

- `app/`: ClickHouse operator HelmRelease and OCIRepository.
- `cluster/`: `ClickHouseCluster/default` (2 replicas, 100Gi `ceph-block`),
  `KeeperCluster/default` (3 replicas, 10Gi `ceph-block`), the
  `clickhouse-init-db` ConfigMap, and the `clickhouse-credentials` ExternalSecret
  from the 1Password `clickhouse` item.

The parked `ks.yaml` keeps the canonical `spec.path`
(`kubernetes/apps/database-system/clickhouse-operator/...`). Move the directory
back before applying it.

## Leftovers

- PVCs backed by `ceph-block`; their provisioned PVs use `reclaimPolicy: Delete`:
  `clickhouse-storage-volume-default-clickhouse-0-0-0`,
  `clickhouse-storage-volume-default-clickhouse-0-1-0` (100Gi each),
  `clickhouse-storage-volume-default-keeper-0-0`, `-1-0`, and `-2-0` (10Gi each).
- CRDs `clickhouseclusters.clickhouse.com` and `keeperclusters.clickhouse.com`
  may remain after the operator chart is removed.
- The 1Password `clickhouse` item. The `clickhouse-credentials`
  ExternalSecret/Secret is pruned with the app.
- No other app consumes this cluster after Langfuse parking; do not unpark it
  without Langfuse unless a new consumer is added.
