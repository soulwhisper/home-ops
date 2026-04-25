---
hide:
  - navigation
  - toc
---

<div align="center">

<img src="https://raw.githubusercontent.com/soulwhisper/home-ops/refs/heads/main/docs/_assets/logo.png" style="width: 144px; height: 144px; vertical-align: middle;"/>

</div>

## <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f680/512.gif" alt="🚀" style="width: 20px; height: 20px; vertical-align: middle;"> My Home Operations repository <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f6a7/512.gif" alt="🚧" style="width: 20px; height: 20px; vertical-align: middle;"> {: style="text-align: center" }

<div align="center">

_... managed by Flux, Renovate and GitHub Actions_ <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f916/512.gif" alt="🤖" style="width: 20px; height: 20px; vertical-align: middle;">

  <p>
    <a href="https://discord.gg/home-operations">
      <img src="https://img.shields.io/discord/673534664354430999?style=for-the-badge&label&logo=discord&logoColor=white&color=blue" alt="Discord">
    </a>
    <a href="https://deepwiki.com/soulwhisper/home-ops">
      <img src="https://deepwiki.com/badge.svg" alt="DeepWiki">
    </a>
  </p>
  <p>
    <a href="https://talos.dev">
      <img src="https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.noirprime.com%2Ftalos_version&style=for-the-badge&logo=talos&logoColor=white&color=blue&label=talos" alt="Talos">
    </a>
    <a href="https://kubernetes.io">
      <img src="https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.noirprime.com%2Fkubernetes_version&style=for-the-badge&logo=kubernetes&logoColor=white&color=blue&label=k8s" alt="Kubernetes">
    </a>
    <a href="https://fluxcd.io">
      <img src="https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.noirprime.com%2Fflux_version&style=for-the-badge&logo=flux&logoColor=white&color=blue&label=flux" alt="Flux">
    </a>
  </p>

  <p>
    <a href="https://github.com/kashalls/kromgo"><img src="https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.noirprime.com%2Fcluster_age_days&style=flat-square&label=Age&color=green" alt="Age"></a>
    <a href="https://github.com/kashalls/kromgo"><img src="https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.noirprime.com%2Fcluster_node_count&style=flat-square&label=Nodes&color=green" alt="Node"></a>
    <a href="https://github.com/kashalls/kromgo"><img src="https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.noirprime.com%2Fcluster_pod_count&style=flat-square&label=Pods&color=green" alt="Pod"></a>
    <a href="https://github.com/kashalls/kromgo"><img src="https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.noirprime.com%2Fcluster_cpu_usage&style=flat-square&label=CPU&color=green" alt="CPU"></a>
    <a href="https://github.com/kashalls/kromgo"><img src="https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.noirprime.com%2Fcluster_memory_usage&style=flat-square&label=Memory&color=green" alt="Memory"></a>
    <a href="https://github.com/kashalls/kromgo"><img src="https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.noirprime.com%2Fcluster_alert_count&style=flat-square&label=Alerts&color=green" alt="Alerts"></a>
  </p>

</div>

### <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f4a1/512.gif" alt="💡" style="width: 16px; height: 16px; vertical-align: middle;"> Overview

This repository serves as a monorepository for the comprehensive infrastructure and Kubernetes cluster powering my home-ops. At its core, it orchestrates a high-performance **Talos Linux** cluster deeply integrated with an **Enterprise Layer 3** network fabric and a **Synology** storage backbone.

The project strictly adheres to **Infrastructure as Code (IaC)** and **GitOps** principles to ensure declarative, repeatable, and version-controlled management across the entire stack—from bare-metal provisioning to application delivery.

### Key Characteristics

- **Kubernetes on Metal:** Built on [Talos Linux](https://www.talos.dev) using M.2 NVMe storage, optimizing for performance and immutability.
- **Enterprise Networking:** Anchored by a managed Layer 3 core switch running **BGP/BFD**, integrating seamlessly with [Cilium](https://github.com/cilium/cilium) for advanced pod networking and **OpenWrt** for edge services (NTP/DNS/VPN/TProxy).
- **Hybrid Storage:** Leveraging **Synology** for centralized NFS/S3 object storage alongside localized high-performance [Rook-Ceph](https://github.com/rook/rook) block storage.
- **Automated Operations:** Powered by [Flux](https://github.com/fluxcd/flux2) for continuous delivery, [GitHub Actions](https://github.com/features/actions) for CI pipelines, and [Renovate](https://github.com/renovatebot/renovate) for dependency management.
