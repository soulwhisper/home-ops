<div align="center">

<img src="https://github.com/soulwhisper/home-ops/blob/main/docs/_assets/logo.png?raw=true" width="144px" height="144px"/>

### <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f680/512.gif" alt="🚀" width="16" height="16"> My Home Operations repository <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f6a7/512.gif" alt="🚧" width="16" height="16">

_... managed by Flux, Renovate and GitHub Actions_ <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f916/512.gif" alt="🤖" width="16" height="16">

[![Discord](https://img.shields.io/discord/673534664354430999?style=for-the-badge&label&logo=discord&logoColor=white&color=blue)](https://discord.gg/home-operations)&nbsp;
[![DeepWiki](https://img.shields.io/badge/deepwiki-purple?style=for-the-badge&label=&logo=deepl&logoColor=white&color=blue)](https://deepwiki.com/soulwhisper/home-ops)

</div>

---

## <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f4a1/512.gif" alt="💡" width="20" height="20"> Overview

This repository serves as a monorepository for the comprehensive infrastructure and Kubernetes cluster powering my home-ops. At its core, it orchestrates a high-performance **Talos Linux** cluster deeply integrated with an **Enterprise Layer 3** network fabric and a **Synology** storage backbone.

The project strictly adheres to **Infrastructure as Code (IaC)** and **GitOps** principles to ensure declarative, repeatable, and version-controlled management across the entire stack—from bare-metal provisioning to application delivery.

### Key Characteristics

- **Kubernetes on Metal:** Built on [Talos Linux](https://www.talos.dev) using M.2 NVMe storage, optimizing for performance and immutability.
- **Networking:** The Layer 3 core switch peers with FRR-K8s over BGP/BFD. [Cilium](https://github.com/cilium/cilium) provides pod networking.
- **Hybrid Storage:** Leveraging **Synology** for centralized NFS/S3 object storage alongside localized high-performance [Rook-Ceph](https://github.com/rook/rook) block storage.
- **Automated Operations:** [Flux](https://github.com/fluxcd/flux2) for GitOps, [GitHub Actions](https://github.com/features/actions) for CI, and [Renovate](https://github.com/renovatebot/renovate) for Synology and CI dependency updates.
- **Kubernetes Lifecycle:** [Dependency upgrades](docs/infrastructure/kubernetes.md#manual-dependency-upgrades) are proposed and reviewed manually so disruptive rollouts can be staged separately.

All configurations are declared as code, promoting reproducibility and enabling seamless updates, scaling, and disaster recovery of the home-ops environment.

---


### 🔏 License

Apache-2.0 — see [LICENSE](LICENSE); attribution, AI-training reservation and
third-party notices in [NOTICE](NOTICE); citation metadata in
[CITATION.cff](CITATION.cff).
