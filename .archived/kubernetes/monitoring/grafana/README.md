# Grafana (archived)

Grafana Operator, the Grafana instance, datasources, vendir-synced dashboards,
and the Grafana MCP server were retired. The native Victoria UIs
(metrics/logs/traces/alert) plus vmalert cover visualization and alerting; the
Grafana MCP tool surface duplicated the Victoria query servers.

This README keeps the retired configuration and the doc sections that were
removed from the active tree so a restore does not require reconstructing them
from history.

## Archived inventory

| Path | Contents |
| --- | --- |
| `app/` | `grafana-operator` HelmRelease (chart `5.25.0`), OCIRepository, 1Password ExternalSecret |
| `cluster/` | `Grafana` CR, datasources, ServiceAccount for MCP, ESO Role/RoleBinding, HTTPRoute, ServiceMonitor, PDB |
| `blueprints/oidc/grafana.yaml` | Authentik OIDC provider, application, and admin-group policy binding |
| `cluster/dashboards/custom/` | The only retained boards: `basement-health.json`, `kopiur-slo.json`, `ALERTS.md`, design notes |
| `cluster/dashboards/{databases,default,kubernetes,network,nodes,storage}/` | Grafana folder/dashboard CRs and ConfigMap generators for the vendir delivery |
| `cluster/dashboards/vendir.yml`, `vendir.lock.yml`, `README.md` | Vendir source list, lock file, and sync strategy |
| `.archived/kubernetes/servitor/mcp/grafana/` | `mcp-grafana` MCPServer, its `mcp-grafana-sa` ExternalSecret, and `ks.yaml` (details in that folder's `README.md`) |
| `.archived/.github/workflows/vendir.yaml` | Retired dashboard-sync workflow, byte-identical to the active copy |

Only `cluster/dashboards/_sources/` (vendir-cached, re-fetchable upstream
data) and the Homepage icon (a rendering asset, not config) were deleted. Every
related config and doc is archived: the vendir files, dashboard
CRs/generators, workflow, MCP server, and OIDC blueprint. The archived
dashboard kustomizations still reference `_sources/`; re-sync it with the
archived workflow before restoring dashboard delivery.

Active wiring removed (not archived as standalone files): monitoring/MCP index
entries, the Authentik blueprint mount, the Homepage icon reference, the
gateway MCP allowlist, the `mcp-fluxcd-extras` Grafana API group, the ToolHive
group wording, the Renovate dashboard manager/group/label, the vendir
yamllint/pre-commit exceptions, NOTICE/REUSE `_sources` license entries, and
Grafana rows/counts in the active docs.

## Retired configuration

### Grafana instance

- Operator chart `grafana-operator@5.25.0`, one operator replica.
- `Grafana` CR: 2 replicas with hostname `topologySpreadConstraints`, PDB
  `minAvailable: 1`, ServiceMonitor on `/metrics`.
- PostgreSQL via the `cnpg` component (`APP: grafana`):
  `postgres-rw.database-system.svc.cluster.local:5432`, database/user
  `grafana`, `postgres-init` init container using the `grafana-pguser` secret.
- Admin and OIDC credentials from the 1Password `grafana` ExternalSecret
  (`admin-user`, `admin-password`, `oidc_client_id`, `oidc_client_secret`).
- Endpoint was `grafana.noirprime.com`; HTTPRoute annotations supplied the
  Homepage entry.

### OIDC

- Authentik provider/application `grafana-oidc-provider` / `grafana`,
  redirect `https://grafana.noirprime.com/login/generic_oauth`, group
  `homelab-admin` bound with the implicit-consent flow.
- Grafana config: `disable_login_form`, `oauth_auto_login`,
  `signout_redirect_url` to Authentik, scopes `openid profile email`,
  `allow_sign_up: true`, `merge_existing_account: true`.
- Role mapping: `contains(groups[*], 'homelab-admin') && 'GrafanaAdmin' || 'Viewer'`.

### Datasources

| Name | Type | Endpoint |
| --- | --- | --- |
| `victoria-metrics` (default) | `victoriametrics-metrics-datasource` | `vmsingle-victoria-metrics-cluster:8428` |
| `victoria-logs` | `victoriametrics-logs-datasource` | `victoria-logs-server:9428` |
| `victoria-traces` | `jaeger` | `victoria-traces:10428/select/jaeger` with traces→logs (±1m, `service.name`) and traces→metrics (±2m) |
| `alertmanager` | `alertmanager` | `vmalertmanager-victoria-metrics-cluster:9093` |
| `prometheus` | `prometheus` | VMSingle:8428, uid `PBFA97CFB590B2093` for grafana.com boards |

Plugins: `grafana-clock-panel`, `victoriametrics-metrics-datasource`,
`victoriametrics-logs-datasource`.

### Dashboards

Vendir synced upstream JSON into `_sources/`; kustomize rendered ConfigMaps
and the Grafana Operator applied them through `GrafanaDashboard` CRs. Folder
set: Default (k8s-system-api-server, blackbox-exporter, envoy-proxy-global,
kopiur-slo, basement-health), Kubernetes (views global/namespaces/nodes/pods),
Storage (ceph cluster/osd/pools), Network (kgateway, cilium-agent), Databases
(cnpg, dragonfly), Nodes (node-exporter-full, smartctl-exporter).

Only the two repo-owned boards are retained. They query vmsingle directly and
remain readable JSON reference; they are not wired to any active dashboard
delivery.

### Renovate dashboard sync (removed)

The active `.renovate/custom.json5` dashboard datasource, manager, package
rules, and the `renovate/grafana-dashboard` label were removed. Re-add these
exact blocks if vendir dashboard sync returns:

```json5
customDatasources: {
  "grafana-dashboards": {
    defaultRegistryUrlTemplate: "https://grafana.com/api/dashboards/{{packageName}}",
    format: "json",
    transformTemplates: [
      '{"releases":[{"version": $string(revision)}], "sourceDirectory": name}',
    ],
  },
}
```

```json5
{
  customType: "regex",
  description: "Update Grafana Dashboard IDs",
  managerFilePatterns: ["(^|/)vendir\\.yml$"],
  matchStrings: [
    "dashboards\\/(?<depName>\\d+)\\/revisions\\/(?<currentValue>\\d+)\\/download",
  ],
  datasourceTemplate: "custom.grafana-dashboards",
  versioningTemplate: "regex:^(?<major>\\d+)$",
  autoReplaceStringTemplate: "dashboards/{{depName}}/revisions/{{newValue}}/download",
}
```

```json5
{
  matchDatasources: ["custom.grafana-dashboards"],
  addLabels: ["renovate/grafana-dashboard"],
  semanticCommitScope: "grafana-dashboards",
  semanticCommitType: "chore",
  commitMessageTopic: "dashboard {{sourceDirectory}}",
  commitMessageExtra: "( {{currentVersion}} → {{newVersion}} )",
},
{
  description: "Vendir Group",
  groupName: "Vendir",
  matchManagers: ["vendir"],
  matchDatasources: ["git-refs", "git-tags", "github-tags"],
  group: {
    commitMessageTopic: "{{{groupName}}} group",
  },
}
```

The label definition removed from `.github/labels.yaml`:

```yaml
- name: renovate/grafana-dashboard
  color: "027fa0"
```

### Grafana MCP

- Image `grafana/mcp-grafana:2.3.0`, streamable HTTP on `:8000`,
  `--disable-write`, host allowlist for the ToolHive headless service.
- `GRAFANA_URL=http://grafana-service.monitoring-system.svc.cluster.local:3000`.
- Token: `GrafanaServiceAccount/mcp-grafana-sa` (Viewer) writes a token Secret
  in `monitoring-system`; the `mcp-grafana-sa` ExternalSecret reads it through
  the `kubernetes` ClusterSecretStore and projects `token` into the MCP pod.
- Group `cluster`; gateway allowlist (removed from active
  `agentgateway/config/mcp/filters.yaml`):

  ```cel
  mcp.tool.name.matches('^mcp-grafana_(search_dashboards|get_dashboard_by_uid|get_dashboard_panel_queries|generate_deeplink|list_datasources)$')
  ```

- `mcp-fluxcd-extras` included `grafana.integreatly.org`; the group description
  named scoped Grafana/Victoria tokens.

MCP-specific files, token flow, gateway filter, and restore steps are recorded
in `.archived/kubernetes/servitor/mcp/grafana/README.md`.

### ESO RBAC note

`cluster/eso-rbac.yaml` declares `Role/eso-store-role` and
`RoleBinding/eso-kubernetes-store-role` in `monitoring-system`, letting the
`security-system/eso-kubernetes` provider read the MCP token Secret. The
removed doc chapter described a staged ownership handoff with
`security-system/external-secrets-cluster`:

- `external-secrets-cluster` declares only `security-system/external-secrets`
  in its Flux `dependsOn`; the store still needs this monitoring
  Role/RoleBinding at runtime.
- Apply object-level prune protection to both objects in both declaring
  Kustomizations before changing ownership.
- For each stage, require both Kustomizations to report the exact merge SHA in
  `status.lastAppliedRevision`, `Ready=True`, and
  `status.observedGeneration == metadata.generation`.
- Remove the duplicate declaration only after both live objects carry the
  protection. Remove the protection only after ownership is unique to
  `grafana-cluster`, then verify both objects retain their UIDs and the token
  sync stays healthy.
- Keep Kustomization pruning enabled throughout.

Restore both declarations and verify the token sync if the handoff is revisited.

### Documentation moved here

| Removed from | Preserved above |
| --- | --- |
| `docs/application/monitoring.md` | Instance, OIDC, datasources, dashboard layout |
| `docs/application/ai.md` | MCP token flow, gateway allowlist, RBAC handoff |
| `docs/infrastructure/kubernetes.md` | Explicit dependencies and ESO ownership |
| `docs/application/authentication.md` | OIDC application row |
| `docs/application/catalog.md` / `kubernetes.md` | Inventory rows and counts |
| `docs/decisions/timezone.md` | Grafana did not receive a process timezone |
| `docs/infrastructure/storage.md` | Kopiur freshness now points at alerts, not dashboards |

## Restore

1. Move this directory back to
   `kubernetes/apps/monitoring-system/grafana` and re-add
   `./grafana/ks.yaml` to the monitoring-system index.
2. Move `blueprints/oidc/grafana.yaml` to
   `kubernetes/apps/security-system/authentik/app/blueprints/oidc/grafana.yaml`,
   add it to the authentik app `kustomization.yaml`, and re-add
   `authentik-blueprints-oidc-grafana` to the Authentik HelmRelease
   `blueprints.secrets`.
3. Re-create the Grafana PostgreSQL role/database (`grafana-pguser`) and the
   1Password entries referenced by `app/externalsecret.yaml`.
4. Restore the MCP server from `.archived/kubernetes/servitor/mcp/grafana` to
   `kubernetes/apps/servitor-apps/mcp/grafana`, add `./grafana/ks.yaml` to
   `kubernetes/apps/servitor-apps/mcp/kustomization.yaml`, rebuild the token
   Secret, and restore the gateway allowlist and `mcp-fluxcd-extras` RBAC entry
   described in that folder's `README.md`.
5. Restore dashboard delivery: move the workflow back to
   `.github/workflows/vendir.yaml`, point its `BASE_DIR` at the restored active
   dashboards path, and run the workflow or its steps. The workflow must also
   rename fetched `*_rev*.json`/`download` files to `dashboard.json` before the
   kustomizations can consume them:

   ```bash
   BASE_DIR=kubernetes/apps/monitoring-system/grafana/cluster/dashboards
   SOURCES_DIR="$BASE_DIR/_sources"
   vendir sync --chdir "$BASE_DIR"
   find "$SOURCES_DIR" -type f \( -name "*_rev*.json" -o -name "download" \) | while read -r FILE; do
     DIR=$(dirname "$FILE")
     mv "$FILE" "$DIR/dashboard.json"
   done
   ```

   Keep the archived dashboard folders/config with the restored app and wire
   the retained custom boards to `GrafanaDashboard` CRs.
6. Re-create the deleted Homepage icon from the upstream artwork and restore
   the HTTPRoute Homepage annotations if Grafana should return to Homepage.
