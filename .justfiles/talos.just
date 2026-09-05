set lazy
set positional-arguments
set quiet
set script-interpreter := ['bash', '-euo', 'pipefail']
set shell := ['bash', '-euo', 'pipefail', '-c']

TALOS_ENDPOINT := `talosctl config info --output json | jq --raw-output '.endpoints[]' | shuf -n 1`

[private]
default:
  @just --list

[doc('Get latest ISO for talos, with https_proxy support')]
[script]
image mode:
  IMAGE_VERSION=$(curl --silent --noproxy '*' https://factory.talos.dev/versions \
    | jq --raw-output 'map(select(test("^v[0-9.]+$"))) | sort_by(. | ltrimstr("v") | split(".") | map(tonumber)) | reverse | .[0]' \
    | tail -n1)
  IMAGE_SCHEMA=$(just _schema {{mode}})
  echo "Latest version: ${IMAGE_VERSION}"
  echo "Image Downloading: talos-{{mode}}-${IMAGE_VERSION}-metal-amd64.iso"
  curl -x "${https_proxy}" --progress-bar -L "https://factory.talos.dev/image/${IMAGE_SCHEMA}/${IMAGE_VERSION}/metal-amd64.iso" \
    -o "/tmp/talos-{{mode}}-${IMAGE_VERSION}-metal-amd64.iso"
  mv "/tmp/talos-{{mode}}-${IMAGE_VERSION}-metal-amd64.iso" "${OPS_DIR}"

[doc('Get schema ID for specific environment')]
[script]
_schema mode:
  SCHEMATIC_ID=$(curl --silent --noproxy '*' -X POST --data-binary @"${TALOS_DIR}/{{mode}}/00-schematic.yaml" https://factory.talos.dev/schematics | jq --raw-output '.id')
  yq --inplace '.schematic_id.{{mode}} = "'"${SCHEMATIC_ID}"'"' "${TALOS_DIR}/version.yaml"
  echo "${SCHEMATIC_ID}"

[doc('Generate talos configuration')]
[script]
generate mode:
  case "{{mode}}" in
    prod) CLUSTER_NAME="main"; CLUSTER_ENDPOINT="https://k8s.homelab.internal:6443" ;;
    test) CLUSTER_NAME="test"; CLUSTER_ENDPOINT="https://172.19.82.101:6443" ;;
    *) echo "❌ Unknown mode: {{mode}} (expected: prod|test)"; exit 1 ;;
  esac
  TALOS_VERSION=$(yq -r '.talos_version' "${TALOS_DIR}/version.yaml")
  K8S_VERSION=$(yq -r '.k8s_version' "${TALOS_DIR}/version.yaml")
  SCHEMATIC_ID=$(just talos _schema {{mode}})
  op inject -i "${TALOS_DIR}/secret.yaml" | talosctl gen config \
    "${CLUSTER_NAME}" "${CLUSTER_ENDPOINT}" \
    --with-docs=false --with-examples=false --force \
    --with-secrets /dev/stdin \
    --talos-version "${TALOS_VERSION}" \
    --kubernetes-version "${K8S_VERSION}" \
    --output "${TALOS_DIR}/clusterconfig"
  for FILE in $(ls ${TALOS_DIR}/{{mode}}/nodes/*.yaml); do
    NODE=$(basename "$FILE" .yaml)
    # apply every numbered patch (10-, 15-, 20-, 30-, ...) in lexical order
    PATCH_ARGS=()
    for PATCH in "${TALOS_DIR}/{{mode}}"/[1-9][0-9]-*.yaml; do
      PATCH_ARGS+=(--patch "@${PATCH}")
    done
    talosctl machineconfig patch "${TALOS_DIR}/clusterconfig/controlplane.yaml" \
      --output "${TALOS_DIR}/clusterconfig/main-$NODE.yaml" \
      "${PATCH_ARGS[@]}" \
      --patch "@${FILE}"
    # inject installer image pinned by version.yaml (talos_version + live schematic id)
    yq --inplace '(select(.kind == "UnattendedInstallConfig")).installer.image = "factory.talos.dev/metal-installer/'"${SCHEMATIC_ID}"':'"${TALOS_VERSION}"'"' \
      "${TALOS_DIR}/clusterconfig/main-$NODE.yaml"
  done
  mkdir -p ~/.talos && cp "${TALOSCONFIG}" ~/.talos/config

[doc('Apply talos configuration to node')]
[script]
apply node *args:
  echo "Applying talos configuration to {{node}}"
  talosctl apply-config --nodes {{node}} --file ${TALOS_DIR}/clusterconfig/main-{{node}}.yaml {{args}}

[doc('Bootstrap talos cluster, INSECURE')]
[script]
_bootstrap_talos:
  for FILE in $(ls ${TALOS_DIR}/clusterconfig/*.yaml); do
    NODE=$(basename "$FILE" .yaml | sed 's/^main-//')
    echo "🚀 Bootstrapping Talos Node: $NODE"
    count=0
    while true; do
      if OUT=$(talosctl apply-config --nodes "$NODE" --file "$FILE" --insecure 2>&1); then
        echo "✅ $NODE accepted configuration."
        break
      fi
      if [[ "$OUT" == *"certificate required"* ]]; then
        echo "ℹ️ $NODE is already configured, skipping."
        break
      fi
      count=$((count + 1))
      if [ $count -ge 12 ]; then
        echo "❌ Failed to apply config to $NODE after 12 attempts:"
        echo "$OUT"
        exit 1
      fi
      echo "⏳ Waiting for $NODE to accept config (attempt $count/12)..."
      sleep 5
    done
  done

[doc('Bootstrap K8S')]
[script]
_bootstrap_k8s:
  echo "🔍 Checking if cluster is already bootstrapped..."
  ETCD_STATUS=$(talosctl -n "{{TALOS_ENDPOINT}}" get service etcd -o json 2>/dev/null | jq -r '.spec.running' || echo "false")
  if [ "$ETCD_STATUS" == "true" ]; then
    echo "✅ Etcd is Running. Cluster implies bootstrapped. Skipping."
    exit 0
  fi
  echo "🚀 Etcd is not Running. Sending bootstrap command..."
  count=0
  until talosctl -n "{{TALOS_ENDPOINT}}" bootstrap 2>&1 | grep -E "AlreadyExists|No error"; do
    count=$((count + 1))
    if [ "$count" -ge 12 ]; then
      echo "❌ Failed to send bootstrap command after 12 attempts."
      exit 1
    fi
    echo "⏳ Retrying bootstrap command (attempt $count/12)..."
    sleep 5
  done
  echo "⏳ Waiting for etcd to come up..."
  count=0
  until [ "$(talosctl -n "{{TALOS_ENDPOINT}}" get service etcd -o json 2>/dev/null | jq -r '.spec.running' || echo "false")" == "true" ]; do
    count=$((count + 1))
    if [ "$count" -ge 60 ]; then
      echo "❌ Etcd did not become ready within 5 minutes."
      exit 1
    fi
    sleep 5
  done
  echo "✅ Bootstrap successful (etcd is running)."
[doc('Wait for apiservers to answer /readyz and nodes to register')]
[script]
_k8s_ready:
  # Helm and kubectl calls after this gate are not retried, so every apiserver
  # must answer first. Nodes come from talosconfig; fall back to an endpoint.
  NODES=$(talosctl config info --output json 2>/dev/null | jq --raw-output '.nodes[]?' || true)
  if [ -z "${NODES}" ]; then NODES="{{TALOS_ENDPOINT}}"; fi
  for NODE in ${NODES}; do
    until [ "$(curl -ks -o /dev/null -w '%{http_code}' --connect-timeout 2 "https://${NODE}:6443/readyz")" == "200" ]; do
      echo "⏳ Waiting for kube-apiserver on ${NODE}..."
      sleep 5
    done
  done
  echo "✅ All apiservers ready."
  # Nodes register as Ready=False until the CNI is healthy — registration is enough here.
  if ! kubectl wait nodes --for=condition=Ready=True --all --timeout=10s &>/dev/null; then
    until kubectl wait nodes --for=condition=Ready=False --all --timeout=10s &>/dev/null; do
      echo "⏳ Waiting for nodes to register..."
      sleep 5
    done
  fi
  echo "✅ All nodes registered."

[doc('Fetch kubeconfig')]
[script]
kubeconfig:
  function retry {
    local retries=$1
    shift
    local count=0
    until "$@"; do
        exit_code=$?
        count=$((count + 1))
        if [ $count -ge $retries ]; then
            echo "❌ Command failed after $retries attempts: $*"
            return $exit_code
        fi
        echo "⚠️  Connection failed. Retrying in 5s... ($count/$retries)"
        sleep 5
    done
    return 0
  }
  retry 20 timeout 5 bash -c "</dev/tcp/{{ TALOS_ENDPOINT }}/6443" 2>/dev/null
  talosctl kubeconfig --nodes {{ TALOS_ENDPOINT }} --force "${KUBECONFIG}"
  mkdir -p ~/.kube && cp "${KUBECONFIG}" ~/.kube/config

[doc('Reboot node')]
[script]
reboot node:
  printf "Reboot node {{node}}? (y/N) "
  read -r confirm
  case "$confirm" in
    y|Y)
      talosctl -n {{node}} reboot -m powercycle
      ;;
    *)
      echo "Cancelled."
      exit 0
      ;;
  esac

[doc('Reset node or cluster')]
[script]
reset node:
  printf "Reset {{node}}? (y/N) "
  read -r confirm
  case "$confirm" in
    y|Y)
      if [ "{{node}}" = "cluster" ]; then
        talosctl reset \
          --system-labels-to-wipe STATE \
          --system-labels-to-wipe EPHEMERAL \
          --system-labels-to-wipe u-local-hostpath \
          --graceful=false --wait=false --reboot
      else
        talosctl -n {{node}} reset --graceful=false --reboot
      fi
      ;;
    *)
      echo "Cancelled."
      exit 0
      ;;
  esac
