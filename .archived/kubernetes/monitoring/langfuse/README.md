# Langfuse

LLM trace backend, archived together with its ClickHouse dependency.

## Why archived

- Its collector filter required `gen_ai.system`, while current spans use
  `gen_ai.provider.name` and `gen_ai.operation.name`; almost every span was
  dropped and `langfuse.traces` / `langfuse.observations` stayed empty.
- Postgres held one project, one user, one API key and five dashboards, with no
  recent UI traffic.
- ClickHouse had no other consumer.

## Data

- `langfuse.events_full` holds guardrail spans; export them before deleting the
  ClickHouse volumes if that audit history is needed.
- The `langfuse` Postgres database and role and the `langfuse` 1Password item
  are independent of this directory; remove them only when discarding that data
  deliberately.
- The ClickHouse PVCs are backed by PVs with `reclaimPolicy: Delete`; deleting
  the PVCs deletes the Ceph volumes.

## Restore

1. Copy this directory to `kubernetes/apps/monitoring-system/langfuse` and
   `clickhouse-operator` to `kubernetes/apps/database-system/`; re-add both to
   the namespace indexes.
2. Reconcile ClickHouse first, then Langfuse.
3. Restore credentials: the 1Password `langfuse` item (admin and `otel_*` keys)
   feeds the `langfuse-otel` ExternalSecret, and the `clickhouse` item feeds
   `clickhouse-credentials`.
4. Restore the collector wiring: the `traces/servitor` pipeline,
   `otlp_http/langfuse` exporter, `basicauth/client` extension, `LANGFUSE_*`
   environment and the `langfuse-otel` ExternalSecret. Match
   `gen_ai.provider.name`, `gen_ai.operation.name`, or
   `IsMatch(name, "^gen_ai\\.")` instead of the `gen_ai.system` condition, and
   add sampling to the `traces/servitor` pipeline before enabling it.
