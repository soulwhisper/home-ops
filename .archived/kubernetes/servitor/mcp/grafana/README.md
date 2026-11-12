# Grafana MCP (archived)

The `mcp-grafana` server was retired with Grafana. Grafana itself, the
`GrafanaServiceAccount` it depended on, and the ESO RBAC are archived under
`.archived/kubernetes/monitoring/grafana/`; its README covers the instance,
OIDC, datasources, and restore order.

## Files

| Path | Contents |
| --- | --- |
| `app/mcpserver.yaml` | `MCPServer/mcp-grafana` definition |
| `app/externalsecret.yaml` | `mcp-grafana-sa` token sync from `monitoring-system` |
| `ks.yaml` | Flux Kustomization; depended on `toolhive-config`, `grafana-cluster`, and `external-secrets-cluster` |

## Retired configuration

- Image `grafana/mcp-grafana:2.3.0`; command `/app/mcp-grafana`.
- Args: `--disable-write`, streamable HTTP on `0.0.0.0:8000`, and the
  ToolHive headless-service host allowlist.
- `GRAFANA_URL=http://grafana-service.monitoring-system.svc.cluster.local:3000`.
- Resources: requests `10m/128Mi`, limits `500m/512Mi`.
- Group `cluster`.

### Token flow

`GrafanaServiceAccount/mcp-grafana-sa` (Viewer) lives in
`.archived/kubernetes/monitoring/grafana/cluster/grafanaserviceaccount.yaml`
and writes a token Secret into `monitoring-system`. The `mcp-grafana-sa`
ExternalSecret reads it through the `kubernetes` ClusterSecretStore and
projects `token` into the MCP pod as `GRAFANA_SERVICE_ACCOUNT_TOKEN`.

### Restore set

The token read needs five declarations that left the active tree with Grafana.
Recreate all of them before enabling the server:

| Object | Namespace | Definition |
| --- | --- | --- |
| `ClusterSecretStore/kubernetes` | cluster-scoped | manifest below |
| `ServiceAccount/eso-kubernetes` | `security-system` | manifest below |
| `Role/eso-store-role` | `monitoring-system` | `.archived/kubernetes/monitoring/grafana/cluster/eso-rbac.yaml` |
| `RoleBinding/eso-kubernetes-store-role` | `monitoring-system` | same file |
| `Kustomization/external-secrets-cluster` | `security-system` (Flux) | path `./kubernetes/apps/security-system/external-secrets/cluster`, `dependsOn: external-secrets`, health-checks `ClusterSecretStore/kubernetes` |

```yaml
# kubernetes/apps/security-system/external-secrets/cluster/clustersecretstore.yaml
apiVersion: external-secrets.io/v1
kind: ClusterSecretStore
metadata:
  name: kubernetes
spec:
  provider:
    kubernetes:
      # Source namespace for all secrets served by this store.
      remoteNamespace: monitoring-system
      server:
        caProvider:
          type: ConfigMap
          name: kube-root-ca.crt
          # read next to the secrets; SA itself stays in security-system
          namespace: monitoring-system
          key: ca.crt
      auth:
        serviceAccount:
          name: "eso-kubernetes"
          namespace: security-system
---
# kubernetes/apps/security-system/external-secrets/cluster/rbac.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: eso-kubernetes
  namespace: security-system
```

Apply the Grafana Role/RoleBinding before expecting the store to become Ready.
Flux orders only `external-secrets` ahead of the store, not the Grafana RBAC,
and the store's validation fails until the provider can read secrets in
`monitoring-system`.

### Gateway filter (removed)

The cluster MCP policy in
`kubernetes/apps/networking-system/agentgateway/config/mcp/filters.yaml`
(`mcp-cluster-filter`, `action: Allow`, default-deny) included:

```cel
mcp.tool.name.matches('^mcp-grafana_(search_dashboards|get_dashboard_by_uid|get_dashboard_panel_queries|generate_deeplink|list_datasources)$')
```

The `mcp-fluxcd-extras` ClusterRole also included the
`grafana.integreatly.org` API group. The ToolHive `cluster` group description
named "scoped Grafana/Victoria* tokens".

## Restore

1. Move this directory back to
   `kubernetes/apps/servitor-apps/mcp/grafana` and re-add
   `./grafana/ks.yaml` to the MCP index.
2. Restore Grafana first, including the `GrafanaServiceAccount` and the
   restore set above. See
   `../../../monitoring/grafana/README.md`.
3. Re-add the gateway allowlist expression above to `mcp-cluster-filter`.
4. Re-add `grafana.integreatly.org` to `mcp-fluxcd-extras` and restore the
   group description.
5. Verify the `mcp-grafana-sa` token sync and a read-only `tools/list` before
   restoring any consumer route.
