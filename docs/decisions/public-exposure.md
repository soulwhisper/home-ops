## ADR - 02 - Public Exposure & Cluster Health Observation

**Context:**
The cluster currently exposes three HTTPRoutes to the public internet via a Cloudflare Tunnel (`cloudflared`) attached to `kgateway-external`: `kromgo` (status badges), `authentik-external` (OIDC for non-existent external consumers), and `flux-webhook` (GitHub push delivery). All other access is VPN-first by design. The exposure surface is therefore vestigial — only `kromgo` carries semantic intent, and that intent is broken: its delivery path traverses the very components it claims to measure (WAN → Cloudflare → tunnel → cluster gateway → kromgo → in-cluster Prometheus), so a grey badge cannot distinguish "cluster down" from "tunnel down" or "WAN down". The observer is bound to the observed.

**Decision:**
I have decided to retire all public exposure and relocate the cluster-health observation surface to an out-of-cluster Gatus instance on the NAS. The `kgateway-external` Gateway resource itself is **retained as an empty scaffold** for topological symmetry with `kgateway-internal`; no HTTPRoutes are attached, and the wildcard certificate remains provisioned.

**Rationale & Comparison:**

**1. Retire `cloudflared` + public HTTPRoutes (Selected):**

- **Correct dependency direction:** Observation source moves to NAS — an independent failure domain. Gatus probes the cluster from outside; when the cluster is down, the dashboard reflects that truthfully rather than going dark itself.
- **Surface reduction:** Removes Cloudflare tunnel, public DNS records, and three HTTPRoutes from the attack surface and from operational knowledge load.
- **VPN-first consistency:** All legitimate access patterns (admin, programmatic, family media) already route via Tailscale/WireGuard + `kgateway-internal`. No application loses functionality.
- **`flux-webhook` accepts pull-mode degradation:** Flux's 1-minute `GitRepository` polling is sufficient; webhook delivery only shaved reconcile latency by seconds.

**2. Migrate `kromgo` → NAS-side Gatus (Selected):**

- **Single binary replaces stack:** Gatus subsumes blackbox probing, uptime storage, badge rendering (`/api/v1/endpoints/.../badge.svg`), Pushover alerting, and a status UI — collapsing what would otherwise be a `blackbox-exporter + victoria-metrics-single + kromgo + alerter` stack on the NAS.
- **Push + pull hybrid:** Critical cluster jobs (DR test, backups, reconcile checks) push success heartbeats to Gatus External Endpoints; Gatus actively probes API server, gateway, and key application HTTPRoutes. Missing pushes and failed probes both trigger Pushover.
- **Information badges sacrificed deliberately:** PromQL-derived numeric badges (CPU %, pod count) are lost. They were decorative; actionable signals (up/down, reachability) are binary and fully covered.

**3. Retain `kgateway-external` Gateway, no HTTPRoutes (Selected):**

- **Topological symmetry:** Gateway-API resource layout mirrors `kgateway-internal`; documentation, diagrams, and operator muscle memory stay coherent.
- **Reversibility:** Future exposure of a single service (e.g., Tailscale Funnel proving insufficient for a media use case) requires attaching one HTTPRoute, not re-bootstrapping the public-facing routing layer.
- **No runtime cost:** A Gateway with zero routes consumes no LB IP beyond the listener and adds no public surface.

**4. Rejected alternatives:**

- **Keep `cloudflared` for `kromgo` only:** Three-component stack to deliver a single broken signal. Net negative.
- **Move `kromgo` to `kgateway-internal`:** Solves auth surface but not the dependency-direction problem; in-cluster observation source remains bound to in-cluster failure modes.
- **Delete `kgateway-external` entirely:** Saves the cert + Gateway manifest but creates an asymmetric topology and a re-bootstrap tax on any future public-exposure decision.

**Known Risks / Mitigation:**

- **Risk:** `kgateway-external` becomes an attractive nuisance — an HTTPRoute is attached absentmindedly, re-introducing public exposure without a decision.
  - **Mitigation:** Empty Gateway manifest carries an inline comment referencing this ADR; future attachment requires an ADR amendment or supersession.
- **Risk:** NAS becomes a new single point for observability.
  - **Mitigation:** NAS is independent of cluster failure domains. For correlated NAS+cluster outages, the missing external-endpoint heartbeats from cluster cron jobs still surface eventually via a separate out-of-tree heartbeat (e.g., Forgejo Actions runner pushing to Gatus from a non-cluster context).
- **Risk:** Public README badges go stale.
  - **Mitigation:** Forgejo Actions periodically renders static SVGs from internal Gatus, commits to the repo. Acceptable freshness loss given badges are vanity, not operational.
- **Cleanup obligation:** Residual `gatus.io/*` annotations on existing HTTPRoutes from a prior Gatus deployment are no-ops and must be removed in the same change set to prevent confusion about whether in-cluster auto-discovery is active. New Gatus configuration is explicit YAML on the NAS — no annotation-driven discovery.

**Scope of change:**

- **Removed:** `cloudflare-tunnel` Kustomization, `kromgo` Kustomization, `external-dns-cloudflare` Kustomization, HTTPRoutes (`kromgo`, `authentik-external`, `flux-webhook`), Cloudflare tunnel and DNS records for the above, Homepage `cloudflared` widget and associated ExternalSecret vars, all `gatus.io/*` annotation residue.
- **Retained:** `kgateway-external` Gateway (empty), `noirprime-com-tls` certificate.
- **Added (out of cluster):** Gatus container on NAS with SQLite persistence, Pushover alerting, declarative endpoint config in a NAS-resident git repository.
