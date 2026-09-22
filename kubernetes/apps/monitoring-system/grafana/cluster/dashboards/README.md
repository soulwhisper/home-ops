## Grafana Dashboard Management Strategy

This document outlines GitOps-centric approach for managing Grafana Dashboards, moving away from direct external URLs to a local synchronization workflow using [vendir](https://carvel.dev/vendir/).

### The Challenge: Limitations of External URLs

Using `GrafanaDashboard` CRs with direct `url` fields (pointing to GitHub/Grafana.com) presents several risks in a production environment:

- **GitOps Violation**: The Git repository is no longer the "Single Source of Truth." The actual dashboard content lives outside Git and can change without a commit history.
- **Stability Risks**: If an upstream repository deletes, renames, or modifies a file (e.g., metric name changes), our dashboards break immediately without warning.
- **Availability**: Cluster scaling or disaster recovery fails if the external source is unreachable (HTTP 404 or downtime).
- **No Audit Trail**: We cannot review changes to the dashboard JSON in Pull Requests because the file isn't stored in our repo.

### The Solution: Local Sync via Vendir

Using **vendir** to fetch upstream dashboards and commit them to a local `_sources/` directory.

#### Workflow

1. **Define**: Declare upstream sources (Git tags or HTTP URLs) in `vendir.yml`.
2. **Sync**: A CI process runs `vendir sync` to download JSON files to `_sources/`.
3. **Deploy**: Kustomize generates `ConfigMaps` from these **local files**. The Grafana Operator watches these ConfigMaps for changes.

#### Directory Structure

```text
dashboards/
├── vendir.yml                  # Source definitions (versions pinned; dropped sources kept commented)
├── _sources/                   # Auto-synced JSON content (DO NOT EDIT)
├── custom/                     # Repo-owned boards (hand-maintained, not vendored)
└── <folder>/                   # One dir per Grafana folder
    ├── grafanadashboard.yaml   # References the local ConfigMap
    ├── grafanafolder.yaml      # Folder definition
    └── kustomization.yaml      # Maps _sources/ or custom/ path to ConfigMap
```

#### Layout: debug-focused (2026-09)

State checks live in native UIs (headlamp, ceph-mgr dashboard, hubble-ui,
agentgateway `:15000/ui`, VM UIs at metrics/logs/traces/alert.noirprime.com);
failures are pushed by vmalert rules. Grafana keeps only trend/correlation
boards that nothing else provides:

| Folder       | Contents |
| ------------ | -------- |
| `Default`    | Must-check, alert-silent domains: k8s-system-api-server, blackbox-exporter, envoy-proxy-global, kopiur-slo (custom) |
| `Kubernetes` | k8s-views global/namespaces/nodes/pods — post-alert drilldown |
| `Storage`    | ceph-cluster/osd/pools — trends behind ceph-mgr dashboard |
| `Network`    | kgateway, cilium-agent — no native control-plane UI exists |
| `Databases`  | cnpg, dragonfly — no native UIs exist |
| `Nodes`      | node-exporter-full, smartctl-exporter — hardware drilldown |

`custom/kopiur-slo.json` replaces the vendored kopiur 0.10.9 board, whose
expressions reference metric families the 0.10.9 operator does not emit.
Note: vendir saves grafana.com HTTP downloads under the literal filename
`download`; the vendir CI workflow renames them to `dashboard.json`
post-sync — `configMapGenerator` paths reference the renamed files.

### Impact Analysis: Maintenance & Recovery

| Aspect                    | External URL (Old)                                                                               | Vendir + Local (New)                                                                                 |
| ------------------------- | ------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------- |
| **Initial Setup**         | **Low** (Just copy-paste URL)                                                                    | **Medium** (Config `vendir.yml` & `kustomization.yaml`)                                              |
| **Long-term Maintenance** | **High Risk**. Upstream changes are invisible until they break the system. Debugging is hard.    | **Low**. Upstream updates are visible via Renovate PRs. Diffs show exactly what changed in the JSON. |
| **Disaster Recovery**     | **Fragile**. Rebuilding the cluster requires external internet access and upstream availability. | **Robust**. The repo is self-contained. Recovery works even in air-gapped environments.              |
| **Breaking Changes**      | "Surprise" breakages on Pod restart.                                                             | Caught during PR review before merging.                                                              |

### How to Update

**Renovate** is configured to watch `vendir.yml`.

1. Renovate detects a new version (e.g., `v1.14.0` -> `v1.15.0`).
2. It creates a PR updating the tag in `vendir.yml`.
3. GitHub Actions triggers `vendir sync` and commits the updated JSON files to the PR.
4. Review the JSON diff and merge.
