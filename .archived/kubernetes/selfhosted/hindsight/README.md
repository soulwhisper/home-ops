# Hindsight (archived)

Retired from the cluster when the service moved to the NAS as a doco-cd compose
stack: `infrastructure/synology/hindsight`. The cluster database held test data
only, so the move was a rebuild, not a dump/restore, and nothing here needs to be
brought back to run memory today.

Hindsight speaks MCP natively at `/mcp/<bank>`, so the ToolHive proxy tier that
fronted it is archived with it (`.archived/kubernetes/servitor/mcp/hindsight`) —
a consumer can call `http://nas.homelab.internal:8888/mcp/<bank>` directly.

## Restoring: bring back all five pieces

1. **App** — `git mv .archived/kubernetes/selfhosted/hindsight kubernetes/apps/selfhosted-apps/hindsight`
   and re-add `- ./hindsight/ks.yaml` to `kubernetes/apps/selfhosted-apps/kustomization.yaml`.

2. **CNPG role** — `kubernetes/apps/database-system/cnpg-operator/cluster/postgres.yaml`,
   under `spec.managed.roles:` on the `Cluster`:

   ```yaml
   managed:
     roles:
       - name: hindsight
         ensure: present
         login: true
         superuser: false
   ```

3. **CNPG database** — same file, appended as its own document. Removing this CR
   is what drops the data — and on 2026-11-12 the cleanup dropped the database
   and the `hindsight` role by hand as well (`DROP DATABASE ... WITH (FORCE)`,
   `DROP ROLE`), because removing the role from `spec.managed.roles` leaves it
   behind. Restoring recreates an empty database:

   ```yaml
   ---
   apiVersion: postgresql.cnpg.io/v1
   kind: Database
   metadata:
     name: hindsight
   spec:
     cluster:
       name: postgres
     name: hindsight
     owner: hindsight
     extensions:
       - name: vector
         ensure: present
       - name: vchord
         ensure: absent
       - name: pgroonga
         ensure: present
   ```

4. **Authentik forward auth** — copy
   `.archived/kubernetes/security/authentik/blueprints/forward/hindsight.yaml`
   back to `kubernetes/apps/security-system/authentik/app/blueprints/forward/`,
   add it to the `authentik-blueprints-forward` file list, and add
   `hindsight-proxy-provider` to the provider list in
   `blueprints/core/outpost-proxy.yaml`. Skipping the outpost binding is the bug
   that makes the outpost fall back to another app's domain.

5. **MCP tier (only if the proxy is actually wanted)** — archived copy at
   `.archived/kubernetes/servitor/mcp/hindsight`, byte-identical to what was
   running (its `remoteUrl` still names `hindsight.selfhosted-apps.svc.cluster.local`,
   which is correct for a restore). Re-add `- ./hindsight/ks.yaml` to
   `kubernetes/apps/servitor-apps/mcp/kustomization.yaml` as well — without that
   index entry both archived Flux Kustomizations stay unapplied. The tier it joined no longer
   exists, so restoring it means also bringing back, from git history: the
   `persona` `MCPGroup` and `VirtualMCPServer`, `mcp-backend-persona`,
   `mcp-persona-auth`, the `/mcp/persona` HTTPRoute, the `mcp_persona` entry in
   the agentgateway `ExternalSecret`, the `vmcp-persona` `ScrapeConfig`, the
   `persona` entry in `cronjob-vmcp-restarter`, and the
   `|| mcp.tool.name.startsWith('mcp-hindsight-ops_')` clause in the agent
   filter. Pointing a consumer at the NAS endpoint directly avoids all of it.

## Why it does not live here any more

It held the only dataset in the homelab that cannot be rebuilt from git. The NAS
is UPS-backed and already received the cluster's barman backups, while the
cluster has no UPS — so the authoritative copy and the live server now share one
durable host. See `infrastructure/synology/hindsight/docker-compose.yml` and
`docs/application/ai.md` § Hindsight.
