# Forgejo Proxy and OIDC (archived)

Forgejo now uses `http://10.10.0.100:9003` as its canonical URL and local
Forgejo accounts for login. The internal HTTPS gateway and Authentik OIDC
integration are archived here. Nothing in this directory is reconciled.

The archived proxy contains the selectorless Service, static EndpointSlice,
and HTTPRoute. The OIDC blueprint is at
`.archived/kubernetes/security/authentik/blueprints/oidc/forgejo.yaml`.
The archived `ks.yaml` retains its original `spec.path`; do not rewrite it.

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
   Restore the same HTTPS URL in the KRR, webhook-relay, cluster Homepage,
   and MCP Forgejo consumers. `COOKIE_SECURE` can remain unset with the HTTPS
   canonical URL.
4. Reconcile Flux and confirm the restored HTTPRoute publishes the
   `git.noirprime.com` A record and its ExternalDNS ownership TXT records.
   These records are ignored by DNSControl and must not be duplicated there.
5. In the Forgejo admin UI, recreate the Authentik authentication source with
   the provider credentials and the callback URL from the restored blueprint.
   Use the local admin account as break-glass; do not remove local login.
6. Verify the networking Kustomization and Authentik HelmRelease are ready,
   then test HTTPS, local login, OIDC login, runner registration, and API
   consumers through the restored gateway.
