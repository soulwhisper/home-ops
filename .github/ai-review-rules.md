# AI review rules — home-ops

Scope the review to the diff. Repo conventions below are intentional; do not
flag them. Repo hard rules are real violations — block on them.

## Block on sight

- Plaintext secrets in any diff; `*.sops.yaml` must stay ciphertext.
- Hand-edited files under `infrastructure/talos/clusterconfig/` (generated).
- Deletion of namespaces / PVCs / StatefulSets / CRDs without an explicit,
  resource-named human approval in the PR discussion.
- Renamed CSI drivers or StorageClasses (names are baked into immutable PV fields).
- Helm values outside the HelmRelease in git.
- `hostUsers: true` or new privileged modes (ADR-03: user namespaces + egress
  CNP is the sandbox boundary; Kata is gone).

## Intentional conventions — NOT findings

- `targetNamespace` injected via `ks.yaml` postBuild (not `metadata.namespace`).
- App-level `ks.yaml` omitting `interval`/`sourceRef`/`prune`/`timeout` —
  `cluster-apps` injects them via `spec.patches` at apply time.
- `$$VAR` in YAML is flux postBuild escape for a literal `$VAR`.
- LLM/MCP traffic routed via agentgateway lanes is required, not a smell.

## Verification context

`prek run -a` (actionlint/zizmor/yamllint/kubeconform) and
`just k8s render-ks <ns> <ks>` are the local gates; CI required check is
`Flux Checks - Success`.
