set lazy
set quiet
set script-interpreter := ['bash', '-euo', 'pipefail']
set shell := ['bash', '-euo', 'pipefail', '-c']

mod forgejo ".justfiles/forgejo.just"
mod infra ".justfiles/infra.just"
mod k8s ".justfiles/k8s.just"
mod talos ".justfiles/talos.just"

export OPS_DIR := justfile_directory()
export K8S_DIR := OPS_DIR / "kubernetes"
export TALOS_DIR:= OPS_DIR / "infrastructure/talos"

# KUBECONFIG := OPS_DIR / "infrastructure/talos/clusterconfig/kubeconfig"
# TALOSCONFIG := OPS_DIR / "infrastructure/talos/clusterconfig/talosconfig"

minijinja_args := '--autoescape none --env --lstrip-blocks --trim-blocks'

[private]
default:
  just --list

[doc('Restore configuration files from backup location')]
[script]
env:
  mise trust
  cp ~/.kube/config "$KUBECONFIG"
  cp ~/.talos/config "$TALOSCONFIG"
  echo "K8S environment restored."

[doc('Lint all files')]
[script]
lint:
  prek run --all-files

[doc('Force Flux to pull in changes from your Git repository')]
[script]
reconcile:
  flux --namespace gitops-system reconcile kustomization gitops-system --with-source

[doc('Bootstrap Cluster with generated prod/test config')]
[script, positional-arguments]
bootstrap mode *targets:
  echo "Make sure you disable all proxies."
  echo "Bootstrapping Talos..."
  just talos _bootstrap_talos "$@"
  echo "completed."
  echo "Bootstrapping K8s..."
  just talos _bootstrap_k8s
  just talos kubeconfig
  echo "completed."
  echo "Waiting for apiservers and node registration..."
  just talos _k8s_ready "${@:2}"
  echo "completed."
  echo "Bootstrapping Apps..."
  just _bootstrap_apps
  echo "completed."
  echo "Cluster bootstrapped. Disable the temporary maintenance DHCP pool."

[script]
_template file:
  minijinja-cli {{file}} {{minijinja_args}} | op inject

[script]
_bootstrap_apps:
  # The vault stores unpadded base64url; yq's @base64d reads the standard alphabet.
  resources=$(just _template "{{K8S_DIR}}/bootstrap/resources.yaml.j2" \
    | yq '(select(.kind == "Secret" and .metadata.name == "onepassword-connect")).stringData."1password-credentials.json" |= (sub("-", "+") | sub("_", "/") | @base64d)')
  printf '%s\n' "$resources" | kubectl apply --server-side -f -
  echo "Syncing Helm Releases..."
  count=0; until helmfile --file "{{K8S_DIR}}/bootstrap/helmfile.yaml" sync --hide-notes; do
    count=$((count + 1))
    if [ $count -ge 5 ]; then exit 1; fi
    echo "Helmfile sync failed, retrying in 10s..."
    sleep 10
  done
