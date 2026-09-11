## ADR - 03 - Workload Sandboxing: user namespaces over kata

**Context:**

The 2026-09 cluster rebuild switched Cilium to `datapathMode: netkit`. This
silently broke every kata workload — the kata shim cannot attach netkit
devices (`Unsupported network interface: netkit` at pod sandbox creation).
Affected: `firecrawl` (headless Chromium on untrusted pages), `karakeep`
(headless crawler), `hermes-agent` (LLM agent executing shell/file tools).

Upstream state: [kata-containers#12159](https://github.com/kata-containers/kata-containers/issues/12159)
is open with no linked PR; the existing PoC covers netkit **L2** mode only
(kata's TC-bridge forwarding is L2), so even a merge would require
`datapathMode: netkit-l2`, surrendering part of the netkit gain.

**Decision:**

Keep netkit. Remove kata entirely (RuntimeClass, `siderolabs/kata-containers`
Talos sysext). Move the sandbox boundary to Kubernetes **user namespaces**
(`hostUsers: false`) plus egress CiliumNetworkPolicies.

**Rationale & Comparison:**

**1. Why user namespaces (selected):**

- Already enabled cluster-wide (GA since k8s 1.30; Talos 1.14 / k8s 1.37
  here — proven live by rsshub, langfuse, dispatcharr running with it).
- Container root maps to an unmapped high UID on the host; all capabilities
  are scoped to the pod's userns. The classic privileged-escape class
  (CAP_SYS_ADMIN/DAC_OVERRIDE/ptrace abuse against the host) is structurally
  dead.
- Firecrawl bonus: Chromium can run its *own* sandbox inside the pod userns
  (nested userns / scoped SYS_ADMIN) instead of `--no-sandbox`.
- Zero extra infrastructure: no sysext, no runtime installer, no VM overhead.

**2. Why kata (removed):**

- Hard-incompatible with netkit today; upstream fix has no timeline and only
  targets netkit-l2. Revisit if #12159 merges.

**3. Why not gVisor (rejected):**

- No official Talos system extension — would mean maintaining a custom
  containerd runtime on an immutable OS.
- runsc's netstack expects Ethernet frames; netkit L3 has no MAC layer, so
  it would force netkit-l2 anyway.

**4. Why not drop netkit for kata (rejected):**

- Netkit earns its keep on the MS-01 nodes (10G×2 LACP, host-routing, BBR):
  earlier BPF execution, no skb clone per packet on the CNI path. Kata was
  defense-in-depth for three workloads; the perf path serves everything.

## Current state

| Layer | State |
|---|---|
| Cilium datapath | `netkit` (L3) — kept |
| kata | **removed** (RuntimeClass + Talos sysext; sysext drops at next node image upgrade) |
| `hostUsers: false` | All app-template workloads **except** NFS consumers |
| Egress CNP | firecrawl, hermes-agent, karakeep, onepassword-connect, toolhive |
| `automountServiceAccountToken: false` | All app-template workloads except `heartbeats`, `homepage` (they have RBAC) |
| Pod Security Admission | **privileged cluster-wide — open decision, see below** |
| seccomp | not explicitly set on most workloads — open sweep |

## Conflicts & removals record

- **kata × netkit** — unresolvable today; kata removed. Rollback path:
  re-add sysext + RuntimeClass + `runtimeClassName` entries, or switch Cilium
  to `netkit-l2` once kata ships support.
- **userns × NFS** — hard conflict: the Linux NFS client does not support
  idmapped mounts, so userns pods cannot mount NFS volumes (k8s docs).
  Excluded workloads: jellyfin, immich, kavita, metube, moviepilot,
  navidrome, qbittorrent(+ui), frigate, scrypted, crafty-controller,
  foundryvtt. Escape hatch: migrate those volumes to cephfs (idmap-capable
  since kernel 6.2; cluster runs 6.18) or wait for kernel NFS idmap support.
- **userns × hostNetwork/hostPID/hostIPC** — invalid combination; no
  workload in scope uses these.
- **restricted PSA × current fixes** — `stirling-pdf`, `bambuddy`,
  `frigate`, `scrypted` require `allowPrivilegeEscalation: true` and/or root
  entrypoints (s6-overlay / file-capability binaries). Moving to
  `restricted` enforcement would require per-namespace exemptions for these.

## Open items

1. **Pod Security Admission defaults** — Talos apiserver currently sets
   `enforce: privileged` (i.e. PSA is a no-op; no namespace enforce labels
   exist). Decision pending: adopt `baseline` as the cluster default with
   `restricted` per-namespace where compatible, plus explicit exemptions for
   the four apps above. Check: `infrastructure/talos/prod/10-general.yaml`
   (`KubeAdmissionControlConfig`).
2. **seccomp sweep** — set `seccompProfile: RuntimeDefault` explicitly
   (containerd does not guarantee it without `SeccompDefault`).
3. **CNP coverage** — extend egress policies beyond the current five apps
   (next candidates: searxng, trendradar, open-notebook — all process
   untrusted internet content).
4. **Kernel watch** — NFS idmapped mounts; kata netkit support (#12159).
