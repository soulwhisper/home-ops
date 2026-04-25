<div align="center">

<img src="https://github.com/soulwhisper/home-ops/blob/main/docs/_assets/logo.png?raw=true" width="144px" height="144px"/>

### <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f680/512.gif" alt="🚀" width="16" height="16"> My Home Operations repository <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f6a7/512.gif" alt="🚧" width="16" height="16">

_... managed by Flux, Renovate and GitHub Actions_ <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f916/512.gif" alt="🤖" width="16" height="16">

[![Discord](https://img.shields.io/discord/673534664354430999?style=for-the-badge&label&logo=discord&logoColor=white&color=blue)](https://discord.gg/home-operations)&nbsp;
[![DeepWiki](https://img.shields.io/badge/deepwiki-purple?style=for-the-badge&label=&logo=deepl&logoColor=white&color=blue)](https://deepwiki.com/soulwhisper/home-ops)

[![Talos](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.noirprime.com%2Ftalos_version&style=for-the-badge&logo=talos&logoColor=white&color=blue&label=talos)](https://talos.dev)&nbsp;
[![Kubernetes](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.noirprime.com%2Fkubernetes_version&style=for-the-badge&logo=kubernetes&logoColor=white&color=blue&label=k8s)](https://kubernetes.io)&nbsp;
[![Flux](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.noirprime.com%2Fflux_version&style=for-the-badge&logo=flux&logoColor=white&color=blue&label=flux)](https://fluxcd.io)

[![Age](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.noirprime.com%2Fcluster_age_days&style=flat-square&label=Age&color=green)](https://github.com/kashalls/kromgo)&nbsp;
[![Node](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.noirprime.com%2Fcluster_node_count&style=flat-square&label=Nodes&color=green)](https://github.com/kashalls/kromgo)&nbsp;
[![Pod](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.noirprime.com%2Fcluster_pod_count&style=flat-square&label=Pods&color=green)](https://github.com/kashalls/kromgo)&nbsp;
[![CPU](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.noirprime.com%2Fcluster_cpu_usage&style=flat-square&label=CPU&color=green)](https://github.com/kashalls/kromgo)&nbsp;
[![Memory](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.noirprime.com%2Fcluster_memory_usage&style=flat-square&label=Memory&color=green)](https://github.com/kashalls/kromgo)&nbsp;
[![Alerts](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.noirprime.com%2Fcluster_alert_count&style=flat-square&label=Alerts&color=green)](https://github.com/kashalls/kromgo)

</div>

---

## <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f4a1/512.gif" alt="💡" width="20" height="20"> Overview

This repository serves as a monorepository for the comprehensive infrastructure and Kubernetes cluster powering my home-ops. At its core, it orchestrates a high-performance **Talos Linux** cluster deeply integrated with an **Enterprise Layer 3** network fabric and a **Synology** storage backbone.

The project strictly adheres to **Infrastructure as Code (IaC)** and **GitOps** principles to ensure declarative, repeatable, and version-controlled management across the entire stack—from bare-metal provisioning to application delivery.

### Key Characteristics

- **Kubernetes on Metal:** Built on [Talos Linux](https://www.talos.dev) using M.2 NVMe storage, optimizing for performance and immutability.
- **Enterprise Networking:** Anchored by a managed Layer 3 core switch running **BGP/BFD**, integrating seamlessly with [Cilium](https://github.com/cilium/cilium) for advanced pod networking and **OpenWrt** for edge services (NTP/DNS/VPN/TProxy).
- **Hybrid Storage:** Leveraging **Synology** for centralized NFS/S3 object storage alongside localized high-performance [Rook-Ceph](https://github.com/rook/rook) block storage.
- **Automated Operations:** Powered by [Flux](https://github.com/fluxcd/flux2) for continuous delivery, [GitHub Actions](https://github.com/features/actions) for CI pipelines, and [Renovate](https://github.com/renovatebot/renovate) for dependency management.

All configurations are declared as code, promoting reproducibility and enabling seamless updates, scaling, and disaster recovery of the home-ops environment.

---

## <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f64f/512.gif" alt="🙏" width="20" height="20"> Gratitude and Thanks

Thanks to all the people who donate their time to the [Home Operations](https://discord.gg/home-operations) Discord community. Be sure to check out [kubesearch.dev](https://kubesearch.dev/) for ideas on how to deploy applications or get ideas on what you could deploy.

I got help from some cool repo like:

- [bjw-s/home-ops](https://github.com/bjw-s/home-ops)
- [onedr0p/home-ops](https://github.com/onedr0p/home-ops)
- [mchestr/home-cluster](https://github.com/mchestr/home-cluster)
- [rafaribe/home-ops](https://github.com/rafaribe/home-ops)

---

### 🔏 License

See [LICENSE](https://github.com/soulwhisper/home-ops/blob/main/LICENSE)
