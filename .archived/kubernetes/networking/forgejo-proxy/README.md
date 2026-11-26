# Forgejo Proxy and OIDC (archived)

## Why the proxy was introduced

[PR #4058](https://github.com/soulwhisper/home-ops/pull/4058) introduced the
proxy to give the NAS-hosted Forgejo a canonical HTTPS endpoint and Authentik
OIDC login. The selectorless Service and static EndpointSlice carried traffic
from the internal gateway to the NAS, while the existing wildcard certificate
terminated TLS at `git.noirprime.com`. This removed recurring cleartext
findings for the webhook-relay and MCP Forgejo consumers and avoided
distributing a custom CA. Direct NAS HTTP remained available as the fallback,
and runner/doc-cd traffic never depended on the proxy. Git token push never
required it.

## Why it is archived

Direct `http://10.10.0.100:9003` access and token push were verified to work.
Keeping a second canonical URL required a selectorless Service, a static
EndpointSlice, an HTTPRoute, an OIDC blueprint, and separate session-cookie
behavior. That complexity had no current benefit, so the active design now has
one direct endpoint and local Forgejo login. This deliberately accepts plain
HTTP on the trusted wired LAN and no Authentik OIDC integration.

The archived proxy contains the selectorless Service, static EndpointSlice,
and HTTPRoute. The OIDC blueprint is at
`.archived/kubernetes/security/authentik/blueprints/oidc/forgejo.yaml`.
The archived `ks.yaml` retains its original `spec.path`; do not rewrite it.
Nothing in this directory is reconciled.

## Restore the gateway and OIDC

1. Move this directory back to
   `kubernetes/apps/networking-system/forgejo-proxy` and re-add
   `./forgejo-proxy/ks.yaml` to
   `kubernetes/apps/networking-system/kustomization.yaml`.
2. Move the archived OIDC blueprint back to
   `kubernetes/apps/security-system/authentik/app/blueprints/oidc/forgejo.yaml`.
   Re-add `./blueprints/oidc/forgejo.yaml` to the Authentik app Kustomization
   and `- authentik-blueprints-oidc-forgejo` to `blueprints.secrets` in its
   HelmRelease.
3. In `infrastructure/synology/forgejo/docker-compose.yml`, restore
   `DOMAIN=git.noirprime.com` and `ROOT_URL=https://git.noirprime.com/`.
   `COOKIE_SECURE` can remain unset with the HTTPS canonical URL. Restore the
   same HTTPS base URL in every active consumer:
   - `kubernetes/apps/monitoring-system/krr/app/cronjob-krr.yaml`
   - `kubernetes/apps/monitoring-system/webhook-relay/app/helmrelease.yaml`
   - `kubernetes/apps/selfhosted-apps/homepage/app/configmap.yaml`
   - `kubernetes/apps/servitor-apps/mcp/forgejo/app/mcpserver.yaml`
   - `infrastructure/synology/homepage/config/services.yaml`
4. Reconcile Flux and confirm the restored HTTPRoute publishes the
   `git.noirprime.com` A record and its ExternalDNS ownership TXT records.
   These records are ignored by DNSControl and must not be duplicated there.
5. In the Forgejo admin UI, recreate the Authentik authentication source with
   the provider credentials and the callback URL from the restored blueprint.
   Use the local admin account as break-glass; do not remove local login.
6. Verify the networking Kustomization and Authentik HelmRelease are ready,
   then test HTTPS, local login, OIDC login, runner registration, and API
   consumers through the restored gateway.
