# Hindsight on the NAS

Agent long-term memory (retain / recall / reflect) for the toolhive MCP proxies
`mcp-hindsight-persona` and `mcp-hindsight-ops`.

## Why it is not in the cluster

Every other workload in this homelab can be rebuilt from git. This one cannot:
the database *is* the memory. The cluster runs without UPS and its Ceph PVCs die
with the hosts, while the NAS is UPS-backed and is already the barman target for
the cluster's databases. So the authoritative copy and the live server now sit
on the same durable host instead of opposite ends of a power cut.

The move also removed four Flux objects (`HelmRelease`, `kustomization`,
`ExternalSecret`, restart `CronJob`), the CloudNativePG dependency, the
`init-db` container and the Ceph RBD layer. In exchange this stack is a plain
compose file that doco-cd reconciles from git, like `versitygw` and `zotregistry`.

## Files

| File | Purpose |
| --- | --- |
| `docker-compose.yml` | postgres (same custom image the cluster used, pinned by digest) + hindsight 1.2.1-slim |
| `hindsight.sops.env` | DB credentials, `HINDSIGHT_API_DATABASE_URL`, and the `llm_omni` / `llm_embedding` / `llm_reranker` lane keys |
| `initdb/10-extensions.sql` | `CREATE EXTENSION vector, pgroonga` — only runs on an empty data dir |

## Data

- Host bind: `/volume3/docker/hindsight/pgdata` → container `/var/lib/postgresql`
- The cluster itself lives one level down, in the image's versioned default
  (`/var/lib/postgresql/18/docker`). `PGDATA` is deliberately not set — that
  default is what lets a future major-version bump sit beside the old cluster
  instead of overwriting it.
- This is a rebuild, not a migration: the previous CNPG database held test data
  and was dropped with the role. There is no restore step.

## Backup

Snapshot the stack directory with the NAS's own schedule (ZFS/BTRFS snapshot of
`/volume3/docker/hindsight`) and add a nightly logical dump to the S3 gateway:

```sh
docker exec hindsight-postgres pg_dump -U hindsight -d hindsight -Fc \
  | aws --endpoint-url http://10.10.0.100:9000 s3 cp - s3://backups/hindsight/$(date +%F).dump
```

Restore onto a fresh volume, then re-run the compose stack — `initdb/` is
skipped once the cluster directory (`/var/lib/postgresql/18/docker`) exists and
is non-empty.

## Rotation

Edit the plaintext env, then `sops -e --input-type dotenv --output-type dotenv`
with the `agentgateway` age recipient and commit. doco-cd redeploys on the next
poll (300 s). Rotating the lane keys means rotating them in the `agentgateway`
1Password item first, then this file.

## Verification

```sh
# DB up
docker exec hindsight-postgres pg_isready -U hindsight -d hindsight
# pgroonga + pgvector present, WAL resource manager loaded
docker exec hindsight-postgres psql -U hindsight -d hindsight \
  -tAc "select extname from pg_extension order by 1;"
docker exec hindsight-postgres psql -U hindsight -d hindsight \
  -tAc "show shared_preload_libraries;"
# MCP reachable from the cluster
kubectl -n servitor-apps port-forward deploy/mcp-hindsight-persona 8080:8080
```

The in-cluster probe `hindsight-nas` (blackbox `tcp_connect`, 60 s) alerts as
`HindsightNasDown` after 5 minutes.

## Known follow-ups

- The `hindsight` container image's healthcheck uses `python3 -c` with a socket
  connect; confirm the slim image actually ships `python3` at that path on first
  deploy (a failing healthcheck does not restart the container, it only marks it
  unhealthy).
- `postgres:18.6` here is the CloudNativePG-patched build. It runs standalone fine
  (standard `docker-entrypoint.sh`, honours `POSTGRES_*`), but if it ever
  misbehaves, swap to `postgres:18` plus a small Dockerfile adding
  `postgresql-18-pgvector` and the Groonga APT repo for pgroonga.
- OTEL tracing is off: the collector's Service IP is unreachable from the NAS.
  Add a LAN-reachable endpoint if traces are wanted.
- The old UI at `memory.noirprime.com` is gone with the app. If it is wanted
  back, put the stack behind Pangolin or a NAS-side reverse proxy; do not
  re-add an in-cluster route for it.
