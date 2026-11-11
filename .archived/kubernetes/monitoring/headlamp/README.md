# Headlamp (archived)

Kubernetes web UI with the Flux plugin and Authentik OIDC. Archived because it
had no gateway traffic; CLI and desktop clients cover the same view.

## Restore

1. Move this directory back to `kubernetes/apps/monitoring-system/headlamp` and
   re-add its `ks.yaml` to the monitoring-system index.
2. Move `blueprints/oidc/headlamp.yaml` to
   `kubernetes/apps/security-system/authentik/app/blueprints/oidc/headlamp.yaml`,
   add `./blueprints/oidc/headlamp.yaml` to the authentik app
   `kustomization.yaml`, and re-add the secret to the Authentik HelmRelease
   `blueprints.secrets`.
3. Merge `config/talos-oidc.yaml` into
   `infrastructure/talos/prod/10-general.yaml` (`KubeAuthenticationConfig`) so
   the apiserver trusts Authentik-issued Headlamp tokens again. The file repeats
   the anonymous block, so it is a complete patch document. Regenerate the node
   configs, then patch **every** control-plane node with the same minimal
   procedure used to remove it:

   ```sh
   patch=kubernetes/apps/monitoring-system/headlamp/config/talos-oidc.yaml
   talosctl -n <node> patch machineconfig --dry-run --patch-file "$patch"
   talosctl -n <node> patch machineconfig --mode no-reboot --patch-file "$patch"
   ```

   While the app is still archived, use
   `.archived/kubernetes/monitoring/headlamp/config/talos-oidc.yaml` instead.

   Do not replace the whole machine config or reboot a node for this change.
4. Re-create the OIDC client credentials in the 1Password `authentik` item if
   they were removed.

The `headlamp-a54d74ce` audience is the API server trust identifier; it must
match the OIDC client in Authentik.
