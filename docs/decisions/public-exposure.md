## ADR - 02 - Public Exposure & Cluster Health Observation

**Context:**
The cluster previously exposed HTTPRoutes to the public internet via a Cloudflare Tunnel (`cloudflared`) attached to `kgateway-external`, including an in-cluster status-badge endpoint whose delivery path traversed the very components it claimed to measure (WAN → Cloudflare → tunnel → cluster gateway → in-cluster monitoring) — the observer bound to the observed. All other access is VPN-first by design.

**Decision:**
I have decided to retire all public exposure except one retained exception — `authentik-external` (OIDC / ForwardAuth / login flows must stay reachable for VPN clients whose IdP session expires). Cluster-health observation and alert delivery stay in-cluster: Alertmanager → webhook-relay → Feishu. There is no external observation surface and none is planned. The `kgateway-external` Gateway resource itself is **retained** for topological symmetry with `kgateway-internal`, and the wildcard certificate remains provisioned. Today it carries two HTTPRoutes: `authentik-external` (auth.noirprime.com — OIDC / ForwardAuth / login flows) and `https-redirect`.

**Rationale & Comparison:**

**1. Retire `cloudflared` + public HTTPRoutes (Selected):**

- **Broken observation removed, not relocated:** The public badge path could not distinguish "cluster down" from "tunnel down" or "WAN down". An out-of-cluster observer on the NAS was deployed and later archived; in-cluster delivery proved sufficient for a solo operator.
- **Surface reduction:** Removes Cloudflare tunnel, public DNS records, and public HTTPRoutes from the attack surface and from operational knowledge load.
- **VPN-first consistency:** All legitimate access patterns (admin, programmatic, family media) already route via Tailscale/WireGuard + `kgateway-internal`. No application loses functionality.
- **`flux-webhook` accepts pull-mode degradation:** Flux's 1-minute `GitRepository` polling is sufficient; webhook delivery only shaved reconcile latency by seconds.

**2. Retain `kgateway-external` Gateway (Selected):**

- **Topological symmetry:** Gateway-API resource layout mirrors `kgateway-internal`; documentation, diagrams, and operator muscle memory stay coherent.
- **Reversibility:** Future exposure of a single service (e.g., Tailscale Funnel proving insufficient for a media use case) requires attaching one HTTPRoute, not re-bootstrapping the public-facing routing layer.
- **No runtime cost:** The two attached routes (`authentik-external`, `https-redirect`) consume no LB IP beyond the listener; the gateway binds an RFC1918 address only, so route attachment alone establishes no public reachability.

**3. Rejected alternatives:**

- **Keep `cloudflared` for the status badges only:** Three-component stack to deliver a single broken signal. Net negative.
- **Status page on `kgateway-internal`:** An in-cluster observation source remains bound to in-cluster failure modes; a badge that requires the cluster to be up to render is vanity, not signal.
- **Delete `kgateway-external` entirely:** Saves the cert + Gateway manifest but creates an asymmetric topology and a re-bootstrap tax on any future public-exposure decision.

**Known Risks / Mitigation:**

- **Risk:** `kgateway-external` becomes an attractive nuisance — an HTTPRoute is attached absentmindedly, re-introducing public exposure without a decision.
  - **Mitigation:** Attaching further public routes requires an ADR amendment or supersession.
- **Risk:** No out-of-cluster observation — a total cluster or WAN outage surfaces only as the absence of Feishu alerts.
  - **Mitigation:** Accepted. Alertmanager → webhook-relay covers every partial failure; for a full outage the missing alerts are themselves the signal (silence = incident).

**Scope of change:**

- **Removed:** `cloudflare-tunnel` Kustomization, `external-dns-cloudflare` Kustomization, the public HTTPRoutes (`flux-webhook`, status badges), Cloudflare tunnel and DNS records for the above, Homepage `cloudflared` widget and associated ExternalSecret vars.
- **Retained:** `kgateway-external` Gateway (with `authentik-external` and `https-redirect` HTTPRoutes), `noirprime-com-tls` certificate.
