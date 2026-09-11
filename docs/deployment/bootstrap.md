## <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f680/512.gif" alt="🚀" style="width: 20px; height: 20px; vertical-align: middle;"> Cluster Bootstrap

Bootstrap a new Talos-based Kubernetes cluster from bare metal. The process
is fully automated through `just` recipes that handle image building, secret
injection, configuration patching, node provisioning, and application delivery.

---

### Prerequisites

| Tool | Purpose | Managed by |
|------|---------|------------|
| [`op`](https://1password.com/downloads/command-line/) | 1Password CLI — injects secrets into Talos and K8s configs | manual |
| [`mise`](https://mise.jdx.dev/) | Runtime version manager — ensures correct tool versions | `mise.toml` (repo root) |
| [`talosctl`](https://www.talos.dev/docs/latest/talos-guides/install/talosctl/) | Talos node interaction | mise |
| [`kubectl`](https://kubernetes.io/docs/tasks/tools/) | Kubernetes cluster interaction | mise |
| [`just`](https://github.com/casey/just) | Task runner — orchestrates all bootstrap phases | mise |

All mise-managed tools auto-install on first use. `mise trust` (included in
the justfile `env` recipe) signs off on the mise config.

---

### Phase 1: Talos Image Build

```shell
just talos image prod
```

Posts the environment's `00-schematic.yaml` to the [Talos Image
Factory](https://factory.talos.dev) to resolve a unique schematic ID, fetches
the latest stable Talos version, then downloads the matching
`metal-amd64.iso`. The ISO is placed in the repo root.

**Production schematic** (`infrastructure/talos/prod/00-schematic.yaml`):

| Extension | Purpose |
|-----------|---------|
| `siderolabs/i915` | Intel GPU driver (QuickSync transcoding) |
| `siderolabs/intel-ucode` | Intel CPU microcode updates |
| `siderolabs/mei` | Intel Management Engine interface |
| `siderolabs/nut-client` | UPS monitoring via NUT |

**Kernel arguments**: `pcie_aspm=off`, `nvme_core.default_ps_max_latency_us=0`,
`i915.enable_guc=3`, `module_blacklist=igc`.

Write the ISO to a USB drive and boot each node into Talos maintenance mode
(pure RAM disk, no install yet).

---

### Phase 2: Config Generation

```shell
just talos generate prod
```

1. **Secret injection**: `op inject` reads `infrastructure/talos/secret.yaml`,
   resolving 1Password references to produce cluster secrets (IDs, tokens, CA
   certs and keys). The resolved YAML is piped to `talosctl gen config`.

   `secret.yaml` is compatible with Talos 1.14 unchanged: the secrets bundle
   schema is identical across 1.13/1.14, and the 1.14 cluster-ID encoding
   alignment (URL-safe → standard base64) is a non-issue because Talos never
   decodes the cluster ID — it is used as an opaque identifier string.

2. **Base generation**: `talosctl gen config` produces `controlplane.yaml` and
   `worker.yaml` in `infrastructure/talos/clusterconfig/` using cluster name
   `main` and API endpoint `https://k8s.homelab.internal:6443`.

3. **Patch layering**: For each node defined in
   `infrastructure/talos/prod/nodes/*.yaml`, the toolchain applies patches in
   lexical order:

   | Order | File | What it configures |
   |-------|------|--------------------|
   | 00 | `00-schematic.yaml` | Schematic ID (Image Factory extension set) |
   | 10 | `10-general.yaml` | Multi-document config: discovery, install, DNS, kubelet/node, scheduler, sysctls, CRI, NUT, NTP, volumes |
   | 20 | `20-mount-hostpath.yaml` | Secondary NVMe disk as `local-cache` XFS volume |
   | 30 | `30-private-mirrors.yaml` | Registry mirrors routing through NAS cache (`nas.homelab.internal:9002`) |
   | — | `nodes/<hostname>.yaml` | Hostname, bond configuration (802.3ad, 10G, MTU 9000), static IP |

   The result is `clusterconfig/main-<hostname>.yaml` per node. The
   `talosconfig` is copied to `~/.talos/config`.

**Key `10-general.yaml` decisions** (Talos 1.14 multi-document model):

- Flannel document is deleted (Cilium is installed later via Helm).
- `KubeCoreDNSConfig` disabled (replaced by Cilium-managed CoreDNS).
- Control-plane taint removed from `KubeNodeConfig` — all three nodes run workloads.
- Discovery uses a custom `DiscoveryServiceConfig` endpoint (`http://10.10.0.100:9300`) instead of Kubernetes-based discovery.
- `ResolverConfig` sets `forwardKubeDNSToHost: true` with a `169.254.116.108/32` loopback link for
  host-to-pod DNS resolution.
- Install is driven by `UnattendedInstallConfig` (Image Factory installer + CEL disk selector).

---

### Phase 3: Node Provisioning

```shell
just bootstrap
```

The top-level `bootstrap` recipe orchestrates phases 3–5. You can also
provision individual nodes:

```shell
just talos apply exarch-01
```

During initial provisioning (`just talos _bootstrap_talos`), each node is
configured **insecurely** (no mutual TLS yet — the node has no prior
identity):

| Behavior | Detail |
|----------|--------|
| Retry count | 5 attempts per node |
| Retry interval | 3 seconds |
| Failure policy | Warns and continues — node may already be booted or rebooting |

```shell
# Under the hood:
talosctl apply-config --nodes <hostname> \
  --file infrastructure/talos/clusterconfig/main-<hostname>.yaml \
  --insecure
```

After config is applied, Talos installs itself to disk and reboots. Wait for
all nodes to come back before proceeding.

---

### Phase 4: Kubernetes Bootstrap

The `just talos _bootstrap_k8s` recipe runs:

1. **Etcd health check**: queries a random control-plane endpoint for etcd's
   running state. If etcd is already running, the bootstrap is skipped — the
   cluster has been bootstrapped previously.

2. **Bootstrap command**: sends `talosctl bootstrap` with retry logic:

   | Behavior | Detail |
   |----------|--------|
   | Retry count | 12 attempts |
   | Retry interval | 5 seconds |
   | Success condition | Response contains `AlreadyExists` or `No error` |

3. **Etcd ready wait**: after the bootstrap command succeeds, polls etcd every
   5 seconds for up to 5 minutes (60 checks) until it reports `running: true`.

```shell
# Bootstrap check flow:
etcd running? ──yes──> skip (already bootstrapped)
     │
     no
     │
     ▼
send bootstrap ──retry×12──> etcd ready? ──retry×60──> done
```

Once etcd is running, fetch the kubeconfig:

```shell
just talos kubeconfig
```

This waits for the API server port (6443) to become reachable (20 retries, 5s
each), then runs `talosctl kubeconfig` and copies the result to
`~/.kube/config`.

---

### Phase 5: Flux Bootstrap

```shell
just _bootstrap_apps
```

Two steps, run sequentially:

1. **Bootstrap resources**: `kubernetes/bootstrap/resources.yaml.j2` is
   templated with [minijinja](https://github.com/mitsuhiko/minijinja), then
   piped through `op inject` to resolve 1Password references
   (`op://DevOps/1password-api/*`). The resulting manifest — a `Namespace`
   and Secret for 1Password Connect — is applied with `kubectl apply
   --server-side`.

2. **Helmfile sync**: `kubernetes/bootstrap/helmfile.yaml` installs the
   cluster's foundation in dependency order with 5 retries (10s interval):

   | Order | Release | Namespace | Purpose |
   |-------|---------|-----------|---------|
   | 1 | `prometheus-crds` | `monitoring-system` | Prometheus Operator CRDs |
   | 2 | `cilium` | `kube-system` | CNI, networking, BGP |
   | 3 | `coredns` | `kube-system` | Cluster DNS |
   | 4 | `spegel` | `kube-system` | P2P image distribution |
   | 5 | `gateway-api-crds` | `kube-system` | Gateway API CRDs |
   | 6 | `external-secrets` | `security-system` | 1Password-backed secrets |
   | 7 | `flux-operator` | `gitops-system` | Flux controller manager |
   | 8 | `flux-instance` | `gitops-system` | Flux Kustomization controllers |

   Each release waits for the previous one to become healthy before
   proceeding. Total timeout per release: 600s.

---

### Phase 6: Initial Sync

```shell
just reconcile
```

Forces Flux to pull the latest commit from the Git repository and apply all
Kustomizations defined under `kubernetes/`:

```shell
flux --namespace gitops-system reconcile kustomization gitops-system --with-source
```

The `--with-source` flag ensures Flux re-fetches the Git source before
reconciling, which is critical on first bootstrap when no prior source
artifact exists.

At this point Flux takes over: it reconciles all Kustomizations recursively,
installing the full application stack defined in the repository. This
includes Cilium networking policies, Authentik, monitoring, storage
provisioning, and every other workload.

---

### Phase 7: Post-Bootstrap

1. **Reboot every node** via BMC/IPMI or Talos API:

   ```shell
   just talos reboot exarch-01
   just talos reboot exarch-02
   just talos reboot exarch-03
   ```

   A cold boot after initial provisioning ensures all kernel modules, sysctl
   tunings, and environment variables propagate correctly from the installed
   image. The reboot recipe uses `-m powercycle` for a hardware-level reset.

2. **Verify cluster health**:

   ```shell
   kubectl get ks -A    # all Kustomizations should be Ready
   kubectl get hr -A    # all HelmReleases should be deployed
   ```

   Expect all Kustomizations to reach `True` within 5–10 minutes as Flux
   works through the dependency tree of ~50+ Kustomizations.

---

### Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `op inject` fails with "not signed in" | 1Password session expired | `eval $(op signin)` then retry |
| `talosctl apply-config` hangs | Node not in maintenance mode | Reboot into Talos ISO, verify network reachability |
| "connection refused" to `k8s.homelab.internal:6443` | DNS not resolving or control plane not ready | Wait for etcd bootstrap; verify DNS record points to node IPs |
| Helmfile sync fails on `cilium` | kube-proxy not disabled, conflicting iptables rules | Verify `KubeProxyConfig` has `enabled: false` in `10-general.yaml` |
| `flux reconcile` stuck | Flux controllers not yet healthy | Wait for `flux-operator` and `flux-instance` HelmReleases; check `kubectl get pods -n gitops-system` |
| Nodes fail to join via discovery | Discovery service unreachable | Verify `http://10.10.0.100:9300` is accessible; check core switch routing |
| Private registry mirrors fail | NAS cache (Dragonfly) not running | Start NAS services first; or temporarily set `skipFallback: false` in `30-private-mirrors.yaml` |

---

### Test Environment

The test cluster runs on VMs inside a separate VLAN. Use `test` instead of
`prod` in all `just talos` commands:

```shell
just talos image test
just talos generate test
just talos apply exarch-01    # uses test configs
```

**Key differences from production**:

| Aspect | Production | Test |
|--------|-----------|------|
| Hypervisor | Bare metal (M.2 NVMe) | Proxmox / VMware VMs |
| Disk | NVMe model selector | RAID1 boot array (`RAIDArrayConfig`, sda+sdb — attach the second disk before ISO boot) |
| API endpoint | `k8s.homelab.internal:6443` | `172.19.82.101:6443` |
| Bond mode | 802.3ad (LACP, 2× physical links) | active-backup (single virtual link) |
| MTU | 9000 (jumbo frames, 10G fabric) | 1500 (standard) |
| Disk | NVMe model selector | `/dev/sda` (virtual disk) |
| Installer image | `factory.talos.dev/…/v*` | `factory.talos.dev/…/v*` |
| Kernel args | `pcie_aspm=off`, `i915.enable_guc=3`, `module_blacklist=igc` | `console=ttyS0`, `lockdown=integrity` (Secure Boot) |
| Registry mirrors | Private NAS cache (5 registries) | `mirror.gcr.io` (docker.io only, fallback allowed) |
| HTTP proxy | None | `http://172.19.82.10:1080` (transparent proxy on edge router) |
| NTP / DNS / NUT | `10.10.0.254` (prod edge router) | `172.19.82.10` (test infra host) |
| Discovery service | `10.10.0.100:9300` | `172.19.82.10:9300` |
| Ephemeral volume | 80 GiB | 512 GiB |
| local-hostpath volume | 140 GiB (shared NVMe) | 256 GiB (virtual disk) |
| local-cache volume | Secondary NVMe via `pci-0000:59:00.0-nvme-1` | Not provisioned |

The test cluster is designed to validate configuration changes before they
reach production. The simpler networking (active-backup bond, no private
mirrors) keeps VM overhead low while still exercising the full GitOps
pipeline.
