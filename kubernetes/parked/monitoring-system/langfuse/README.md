# Langfuse (parked)

Langfuse and its ClickHouse dependency are parked. The application manifests
remain in this directory, but no Kustomization applies them. The parked
`ks.yaml` keeps the canonical `spec.path`, so move the directory back before
applying it.

## Why parked

- Langfuse held no LLM traces. The collector's `traces/servitor` filter required
  `gen_ai.system`, while current spans use `gen_ai.provider.name` and
  `gen_ai.operation.name`; 1,392,994 spans were dropped in seven days and only 32
  guardrail spans reached Langfuse.
- `langfuse.traces` and `langfuse.observations` were empty. `events_full` held
  1,393 guardrail spans from 2026-10-16 to 2026-11-06.
- Postgres held one project, one user, one API key, five dashboards, and no
  prompts or datasets. There was no recent UI traffic after the 2026-11-08 setup.
- ClickHouse had no other consumer.

## Related active changes

- `kubernetes/apps/monitoring-system/kustomization.yaml` and
  `kubernetes/apps/database-system/kustomization.yaml`: the `langfuse` and
  `clickhouse-operator` entries were removed.
- `kubernetes/apps/monitoring-system/opentelemetry-collector/app/helmrelease.yaml`:
  the `traces/servitor` pipeline, `otlp_http/langfuse` exporter,
  `basicauth/client` extension, `LANGFUSE_*` environment, and `filter/gen_ai`
  processor were removed. `traces/app` still exports to VictoriaTraces.
- `kubernetes/apps/monitoring-system/opentelemetry-collector/app/externalsecret.yaml`:
  removed together with its `kustomization.yaml` entry.
- `kubernetes/apps/monitoring-system/opentelemetry-collector/ks.yaml`: the
  `dependsOn langfuse` entry was removed.
- `kubernetes/apps/security-system/kyverno/policies/validatingpolicy-audit-pod-deletes.yaml`:
  the ClickHouse operator service-account exclusion was removed.
- `kubernetes/apps/servitor-apps/mcp/fluxcd/app/rbac.yaml`: the `clickhouse.com`
  API group was removed.
- `kubernetes/apps/monitoring-system/grafana/cluster/dashboards/custom/ALERTS.md`:
  the ClickHouse log-volume note was removed.
- `renovate.json5` now ignores `kubernetes/parked/**`; the Langfuse and
  ClickHouse groups and the Langfuse auto-merge rule were removed.
- `agentgateway` and `open-webui` telemetry comments were updated for the
  VictoriaTraces-only pipeline.
- `docs/application/monitoring.md`, `docs/application/ai.md`, and
  `docs/application/catalog.md` were updated. Historical decision records under
  `docs/decisions/` still mention Langfuse; they are records, not active
  configuration.

## Leftovers after Flux prune

Flux prunes the Kustomizations and their resources on merge. Verify, then clean
up manually:

1. **Postgres database and role.** `langfuse` (15 MB) and role `langfuse` were
   created by the `postgres-init` init container, not by a `Database` CR. They
   are not deleted by parking. Drop them only after confirming no consumer:

   ```sql
   \c postgres
   DROP DATABASE langfuse WITH (FORCE);
   DROP ROLE langfuse;
   ```
2. **ClickHouse PVCs.** The PV reclaim policy is `Delete`:
   `clickhouse-storage-volume-default-clickhouse-0-0-0` and
   `clickhouse-storage-volume-default-clickhouse-0-1-0` (100Gi each),
   `clickhouse-storage-volume-default-keeper-0-0`, `-1-0`, and `-2-0` (10Gi each).
   Delete only when the data is no longer needed; deleting the PVCs deletes the
   Ceph volumes.
3. **ClickHouse CRDs.** `clickhouseclusters.clickhouse.com` and
   `keeperclusters.clickhouse.com` may remain after the operator chart is
   removed. Delete them if no reinstall is planned.
4. **ClickHouse credentials.** The `clickhouse-credentials`
   Secret/ExternalSecret is pruned with the app; the 1Password `clickhouse` item
   (`langfuse_password`, `default_password`) remains.
5. **Object storage.** The `ceph-bucket-langfuse` ObjectBucketClaim has the
   `objectbucket.io/finalizer` and references the `langfuse` bucket. Verify the
   bucket is deleted; remove it manually if it is retained.
6. **1Password.** Remove the `langfuse` item (admin and `otel_*` keys) when it
   is no longer needed. The shared `app-user` and `encryption-cipher` items are
   used by other apps and must stay.
7. **DNS and Homepage.** The `langfuse.noirprime.com` HTTPRoute is pruned;
   verify external-dns removes the record. The Homepage entry comes from the
   route annotation and disappears with it.
8. **Collector secret.** The `langfuse-otel` Secret in `monitoring-system` is
   pruned with the collector ExternalSecret.

The historical `.tmp-recovery-2026-09-24.md` still mentions Langfuse and
ClickHouse; it is a recovery note, not active configuration.

## Data

Langfuse data was disposable: 1,393 guardrail spans in
`langfuse.events_full`, no traces or observations, and no prompts or datasets.
Export the guardrail spans before deleting ClickHouse if their audit history is
needed:

```sql
SELECT * FROM langfuse.events_full
```

The ClickHouse `system` tables hold only ClickHouse's own logs.

## Unpark

1. Move `kubernetes/parked/database-system/clickhouse-operator` back to
   `kubernetes/apps/database-system/clickhouse-operator` and restore its entry in
   `kubernetes/apps/database-system/kustomization.yaml`.
2. Move this directory back to
   `kubernetes/apps/monitoring-system/langfuse` and restore its entry in
   `kubernetes/apps/monitoring-system/kustomization.yaml`.
3. Keep the existing `ks.yaml` paths. Reconcile ClickHouse first
   (`rook-ceph-cluster` → `clickhouse-operator` → `clickhouse-cluster`), then
   Langfuse (`clickhouse-cluster`, `cnpg-cluster`, `dragonfly-operator`).
4. Restore the collector wiring: the `traces/servitor` pipeline,
   `otlp_http/langfuse` exporter, `basicauth/client`, `LANGFUSE_*` environment,
   and the `langfuse-otel` ExternalSecret. **Do not restore the old
   `filter/gen_ai` condition unchanged.** It checks `gen_ai.system`, but current
   spans use `gen_ai.provider.name` and `gen_ai.operation.name`. Match
   `gen_ai.provider.name`, `gen_ai.operation.name`, or `IsMatch(name, "^gen_ai\\.")`,
   and add sampling to the servitor pipeline before enabling it.
5. Restore the Kyverno service-account exclusion only if the ClickHouse operator
   needs the pod-delete exception. Restore `clickhouse.com` in the fluxcd MCP
   RBAC only if it must read ClickHouse CRs.
6. Restore the Renovate groups and Langfuse auto-merge rule only when the app is
   active again, and only after removing the parked-path ignore for this app.
7. Re-add the 1Password `langfuse` and `clickhouse` items if they were removed.
8. A dropped Postgres database is recreated empty by `postgres-init`; ClickHouse
   data is empty after a fresh cluster.
