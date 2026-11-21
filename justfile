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
  if ! just bootstrap-apps; then
    echo "Retry the app phase with 'just bootstrap-apps'; do not rerun 'just bootstrap'." >&2
    exit 1
  fi
  echo "completed."
  echo "Cluster bootstrapped. Disable the temporary maintenance DHCP pool."

[doc('Install or retry bootstrap apps on the current Kubernetes cluster')]
[script]
bootstrap-apps:
  secret=$(kubectl --namespace security-system get secret onepassword-connect --ignore-not-found -o name)
  if [[ -z "$secret" ]]; then
    if ! rendered=$(timeout 60s op inject --in-file "{{K8S_DIR}}/bootstrap/onepassword-connect.yaml"); then
      echo "1Password injection failed or timed out; no resources created." >&2
      exit 1
    fi
    # The vault stores unpadded base64url; yq's @base64d reads the standard alphabet.
    if ! resource=$(yq '.stringData."1password-credentials.json" |= (sub("-", "+") | sub("_", "/") | @base64d)' <<< "$rendered" 2>/dev/null) ||
      ! yq -o=json '.' <<< "$resource" 2>/dev/null |
        jq -es 'length == 1 and (.[0] |
          .apiVersion == "v1" and .kind == "Secret" and
          .metadata.namespace == "security-system" and .metadata.name == "onepassword-connect" and
          (.stringData.token | type == "string" and test("^\\S+$") and . != "0" and (startswith("op://") | not)) and
          (.stringData."1password-credentials.json" | fromjson | type == "object" and length > 0)
        )' >/dev/null 2>&1; then
      echo "1Password Connect requires a resolved token and a non-empty JSON credentials object; no resources created." >&2
      exit 1
    fi
    namespace=$(kubectl get namespace security-system --ignore-not-found -o name)
    if [[ -z "$namespace" ]]; then
      kubectl create namespace security-system
    fi
    printf '%s\n' "$resource" | kubectl create -f -
  fi
  mise install helmfile
  helmfile_bin=$(mise which helmfile)
  echo "Syncing Helm Releases..."
  count=0; until "$helmfile_bin" --file "{{K8S_DIR}}/bootstrap/helmfile.yaml" sync --hide-notes; do
    count=$((count + 1))
    if [ $count -ge 5 ]; then exit 1; fi
    echo "Helmfile sync failed, retrying in 10s..."
    sleep 10
  done
