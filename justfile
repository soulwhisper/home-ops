set lazy
set quiet
set script-interpreter := ['bash', '-euo', 'pipefail']
set shell := ['bash', '-euo', 'pipefail', '-c']

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

[doc('Bootstrap Cluster')]
[script]
bootstrap:
  echo "Make sure you disable all proxies."
  echo "Bootstrapping Talos..."
  just talos _bootstrap_talos
  echo "completed."
  echo "Bootstrapping K8s..."
  just talos _bootstrap_k8s
  just talos kubeconfig
  echo "completed."
  echo "Bootstrapping Apps..."
  just _bootstrap_apps
  echo "completed."
  echo "Cluster bootstrapped. Please reboot nodes."

[script]
_template file:
  minijinja-cli {{file}} {{minijinja_args}} | op inject

[script]
_bootstrap_apps:
  just _template "{{K8S_DIR}}/bootstrap/resources.yaml.j2" | kubectl apply --server-side -f -
  echo "Syncing Helm Releases..."
  count=0; until helmfile --file "{{K8S_DIR}}/bootstrap/helmfile.yaml" sync --hide-notes; do
    count=$((count + 1))
    if [ $count -ge 5 ]; then exit 1; fi
    echo "Helmfile sync failed, retrying in 10s..."
    sleep 10
  done
