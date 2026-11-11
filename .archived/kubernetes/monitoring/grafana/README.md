# Grafana (archived)

Grafana Operator, the Grafana instance, datasources, vendir-synced dashboards,
and the Grafana MCP server were retired. The native Victoria UIs
(`metrics`/`logs`/`traces`/`alert`) plus vmalert cover visualization and
alerting; the Grafana MCP tool surface duplicated the Victoria query servers.

Vendir sources, `GrafanaDashboard`/`GrafanaFolder` CRs, and the dashboard
ConfigMap generators were removed; the vendir CI workflow is archived under
`.archived/.github/workflows/vendir.yaml`. The only
retained dashboards are the two repo-owned boards in
`cluster/dashboards/custom/`:

| Board | Purpose |
| --- | --- |
| `basement-health.json` | Failure-revealing baseline health and SLO view |
| `kopiur-slo.json` | Backup freshness, failures, size, and duration |
| `ALERTS.md` | Panel-to-alert coverage map and planned SLO rules |
| `README.md` | Design notes and known data caveats |

The remaining `app/` and `cluster/` manifests are kept for reference only.
They are not reconciled (`Flux` reads `kubernetes/` only) and the dashboard
generators that referenced `_sources/` no longer exist.

## Restore

1. Move this directory back to
   `kubernetes/apps/monitoring-system/grafana` and re-add
   `./grafana/ks.yaml` to the monitoring-system index.
2. Move `blueprints/oidc/grafana.yaml` to
   `kubernetes/apps/security-system/authentik/app/blueprints/oidc/grafana.yaml`,
   add it to the authentik app `kustomization.yaml`, and re-add
   `authentik-blueprints-oidc-grafana` to the Authentik HelmRelease
   `blueprints.secrets`.
3. Restore the MCP server from `.archived/kubernetes/servitor/mcp/grafana`,
   re-add it to the MCP index, and restore its gateway allowlist and
   `mcp-fluxcd` RBAC entry.
4. Re-create dashboard delivery. The vendored JSON and vendir workflow were
   deleted; re-import upstream boards or wire the retained custom boards to
   new `GrafanaDashboard` CRs.
5. Re-add the Homepage icon and HTTPRoute annotations if Grafana should return
   to Homepage.
6. Re-create the Grafana PostgreSQL role/database and 1Password OIDC entries if
   they were removed.
