# ClickHouse operator and cluster

ClickHouse operator and cluster used by Langfuse. Langfuse was the only
consumer, so the stack has no active dependents and is archived with it.

## Contents

- `app/`: ClickHouse operator HelmRelease and OCIRepository.
- `cluster/`: `ClickHouseCluster/default` (2 replicas, 100Gi `ceph-block`),
  `KeeperCluster/default` (3 replicas, 10Gi `ceph-block`), the
  `clickhouse-init-db` ConfigMap, and the `clickhouse-credentials` ExternalSecret
  from the 1Password `clickhouse` item.

`ks.yaml` keeps the canonical `spec.path`; restore this directory to
`kubernetes/apps/database-system/clickhouse-operator` before applying it.

## Data

- The provisioned PVs use `reclaimPolicy: Delete`; deleting the PVCs deletes the
  Ceph volumes:
  `clickhouse-storage-volume-default-clickhouse-0-0-0`,
  `clickhouse-storage-volume-default-clickhouse-0-1-0` (100Gi each),
  `clickhouse-storage-volume-default-keeper-0-0`, `-1-0`, and `-2-0` (10Gi each).
- CRDs `clickhouseclusters.clickhouse.com` and `keeperclusters.clickhouse.com`
  and the 1Password `clickhouse` item may remain.
- Do not run this cluster without a consumer; Langfuse is the only one.
