set quiet := true
set shell := ['bash', '-euo', 'pipefail', '-c']

[private]
default:
  @just --list

[doc('Browse a PVC')]
browse-pvc ns pvc:
  kubectl browse-pvc -n {{ns}} -i alpine:latest {{pvc}}

[doc('Open a shell on a node')]
node-shell node:
  kubectl debug node/{{node}} -n default -it --image='alpine:latest' --profile sysadmin
  kubectl get pods -n default | awk '/node-debugger-/ {print $1}' | xargs kubectl delete pod -n default

[doc('Prune pods in Failed, Pending, or Succeeded state')]
prune-pods:
  for phase in Failed Pending Succeeded; do \
    kubectl delete pods -A --field-selector status.phase="$phase" --ignore-not-found=true; \
  done

[doc('Prune revision history')]
prune-rs:
  kubectl get rs --no-headers -A | while read -r ns name desired _; do \
    if [ "$desired" = "0" ]; then \
      kubectl delete rs -n "$ns" "$name"; \
    fi; \
  done

[doc('Render local Flux Kustomization')]
render-ks ns ks:
  uvx flux-local build ks --namespace "{{ ns }}" --path "$K8S_DIR/flux/cluster" "{{ ks }}"

[doc('Apply local Flux Kustomization')]
apply-ks ns ks:
  just render-ks "{{ ns }}" "{{ ks }}" \
  | kubectl apply --force-conflicts --server-side --field-manager=kustomize-controller -f -

[doc('Delete local Flux Kustomization')]
delete-ks ns ks:
  just render-ks "{{ ns }}" "{{ ks }}" \
  | kubectl delete -f -

[doc('Sync single Flux HelmRelease')]
sync-hr ns name:
  kubectl -n {{ns}} annotate --field-manager flux-client-side-apply --overwrite hr {{name}} reconcile.fluxcd.io/requestedAt="$(date +%s)" reconcile.fluxcd.io/forceAt="$(date +%s)"; \

[doc('Sync single Flux Kustomizations')]
sync-ks ns name:
  kubectl -n {{ns}} annotate --field-manager flux-client-side-apply --overwrite ks {{name}} reconcile.fluxcd.io/requestedAt="$(date +%s)"; \

[doc('Sync single ExternalSecret')]
sync-es ns name:
  kubectl -n {{ns}} annotate --field-manager flux-client-side-apply --overwrite es {{name}} force-sync="$(date +%s)"; \

[doc('Sync all Flux HelmReleases')]
sync-all-hr:
  kubectl get hr --no-headers -A | while read -r ns name _; do \
    just sync-hr "$ns" "$name"; \
  done

[doc('Sync all Flux Kustomizations')]
sync-all-ks:
  kubectl get ks --no-headers -A | while read -r ns name _; do \
    just sync-ks "$ns" "$name"; \
  done

[doc('Sync all ExternalSecrets')]
sync-all-es:
  kubectl get es --no-headers -A | while read -r ns name _; do \
    just sync-es "$ns" "$name"; \
  done

[doc('Snapshot VolSync ReplicationSource')]
snapshot ns name:
  kubectl -n "{{ ns }}" patch replicationsources "{{ name }}" --type merge -p '{"spec":{"trigger":{"manual":"$(date +%s)"}}}'

[doc('Snapshot all VolSync ReplicationSources')]
snapshot-all:
  kubectl get replicationsources --no-headers -A | while read -r ns name _; do \
    just snapshot "$ns" "$name"; \
  done
