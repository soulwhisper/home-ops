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
  curl --silent --noproxy '*' -X POST --data-binary @"${TALOS_DIR}/{{mode}}/00-schematic.yaml" https://factory.talos.dev/schematics | jq --raw-output '.id'

[doc('Generate talos configuration')]
[script]
generate mode:
  op inject -i "${TALOS_DIR}/secret.yaml" | talosctl gen config \
    main https://k8s.homelab.internal:6443 \
    --with-docs=false --with-examples=false --force \
    --with-secrets /dev/stdin \
    --output "${TALOS_DIR}/clusterconfig"
  for FILE in $(ls ${TALOS_DIR}/{{mode}}/nodes/*.yaml); do
    NODE=$(basename "$FILE" .yaml)
    talosctl patch machineconfig "${TALOS_DIR}/clusterconfig/controlplane.yaml" \
      --output "${TALOS_DIR}/clusterconfig/main-$NODE.yaml" \
      --patch "${TALOS_DIR}/{{mode}}/10-general.yaml" \
      --patch "${TALOS_DIR}/{{mode}}/nodes/$NODE.yaml"
  done
  mkdir -p ~/.talos && cp "${TALOSCONFIG}" ~/.talos/config

[doc('Apply talos configuration to node')]
[script]
apply node *args:
  @echo "Applying talos configuration to {{node}}"
  talosctl apply-config --nodes {{node}} --file ${TALOS_DIR}/clusterconfig/main-{{node}}.yaml {{args}}

[doc('Bootstrap talos cluster, INSECURE')]
[script]
_bootstrap_talos:
  for FILE in $(ls ${TALOS_DIR}/clusterconfig/*.yaml); do
    NODE=$(basename "$FILE" .yaml | sed 's/^main-//')
    echo "🚀 Bootstrapping Talos Node: $NODE"
    count=0
    until talosctl apply-config --nodes "$NODE" --file "$FILE" --insecure 2>/dev/null; do
      exit_code=$?
      count=$((count + 1))
      if [ $count -ge 5 ]; then
          echo "⚠️ Failed to apply config to $NODE after 5 attempts. Assuming node might be rebooting or already ready. Continuing..."
          break
      fi
      echo "⏳ Waiting for $NODE to accept config (Attempt $count/5)..."
      sleep 3
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
  echo "🚀 Etcd is Running. Attempting bootstrap..."
  count=0
  until talosctl -n "{{TALOS_ENDPOINT}}" bootstrap 2>&1 | grep -E "AlreadyExists|No error"|| [ "$count" -ge 12 ]; do
    echo "⏳ Sending bootstrap command (Attempt $((++count))/12)..."
        sleep 5
    done
    FINAL_RUNNING=$(talosctl -n "{{TALOS_ENDPOINT}}" get service etcd -o json 2>/dev/null | jq -r '.spec.running' || echo "false")
    if [ "$FINAL_RUNNING" == "true" ]; then
       echo "✅ Bootstrap successful (Etcd is running)."
       exit 0
    else
       if [ "$count" -ge 12 ]; then
           echo "❌ Failed to bootstrap cluster. Etcd is not running."
           exit 1
       fi
    fi

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
