## <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f331/512.gif" alt="🌱" style="width: 20px; height: 20px; vertical-align: middle;"> Kubernetes

The Kubernetes cluster is deployed using [Talos](https://www.talos.dev), leveraging M.2 NVMe SSDs across all nodes for high-performance storage.

### Core Components

- [cert-manager](https://github.com/cert-manager/cert-manager): Automates the management and issuance of TLS certificates.
- [cilium](https://github.com/cilium/cilium): eBPF-based CNI providing networking, security, and observability with Gateway API support.
- [cloudflared](https://github.com/cloudflare/cloudflared): Stable tunnel for secure ingress.
- [cloudnative-pg](https://github.com/cloudnative-pg/cloudnative-pg): Kubernetes-native PostgreSQL operator with VectorChord support and S3 backup integration.
- [external-dns](https://github.com/kubernetes-sigs/external-dns): Split-horizon DNS management syncing records to AdGuard (internal) and Cloudflare (external).
- [external-secrets](https://github.com/external-secrets/external-secrets): Syncs Kubernetes secrets from [1Password Connect](https://github.com/1Password/connect).
- [frr-k8s](https://github.com/metallb/frr-k8s): Manages BGP sessions and BFD for high-availability networking.
- [rook-ceph](https://github.com/rook/rook): Distributed block storage for peristent storage.
- [spegel](https://github.com/spegel-org/spegel): Stateless cluster local OCI registry mirror.
- [victoria-metrics](https://github.com/VictoriaMetrics/VictoriaMetrics): High-performance monitoring and logging stack (victoria-logs).
- [volsync](https://github.com/backube/volsync): Backup and recovery of persistent volume claims.

### GitOps

[Flux](https://github.com/fluxcd/flux2) watches the clusters in my kubernetes folder (see Directories below) and ensures that my clusters are updated based on the state of the corresponding Git repository.

In my setup, Flux operates by recursively scanning the `kubernetes/apps` folder until it identifies the top-level `kustomization.yaml` file within each directory. This file serves as the entry point for Flux, and it lists all the resources to be applied to the cluster. Typically, the `kustomization.yaml` contains a namespace resource and one or more Flux kustomizations (`ks.yaml`). These kustomizations govern the deployment of specific resources, including `HelmRelease` resources or other application-specific resources, which Flux subsequently applies to the cluster.

[Renovate](https://github.com/renovatebot/renovate) continuously monitors my **entire** repository for dependency updates. When an update is detected, Renovate automatically creates a pull request. Upon merging these pull requests, Flux is triggered to apply the changes to my clusters, ensuring that my environments are always aligned with the latest desired state as defined in Git.

This GitOps workflow enables a fully automated and declarative approach to managing both the infrastructure and application deployments across my Kubernetes clusters. By relying on Flux and Renovate, I can ensure that updates are consistent, repeatable, and seamlessly applied, maintaining the integrity and reliability of the cluster without manual intervention.

### Directories

This Git repository contains following directories.

```sh
📁 kubernetes
├── 📁 apps                   # applications
├── 📁 bootstrap              # bootstrap procedures
├── 📁 components             # re-useable components
└── 📁 flux                   # flux configuration
📁 infrastructure
├── 📁 dnscontrol             # dns configuration
├── 📁 switch                 # switch configuration
├── 📁 synology               # synology configuration
└── 📁 talos                  # talos configuration
```
