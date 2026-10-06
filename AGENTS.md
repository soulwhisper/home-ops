# AGENTS.md

Single-cluster Talos homelab. Everything under `kubernetes/` is Flux-reconciled;
cluster state follows git. Direct `kubectl apply/edit` on managed objects is drift
and will be reverted.

## Hard rules (violations = block)

- **No plaintext secrets, ever.** Secrets are SOPS-encrypted `*.sops.yaml`; a diff
  showing plaintext fields is a leak — stop and flag it. New secrets: 1Password
  item + `ExternalSecret` (ClusterSecretStore `onepassword`).
- **`infrastructure/talos/clusterconfig/` is generated output.** Edit
  sources/patches and regenerate; never hand-edit generated files.
- **No deletions of namespaces, PVCs, StatefulSets, CRDs** without an explicit,
  resource-named human approval in the PR discussion.
- **Never rename CSI drivers / StorageClasses** — names are baked into immutable
  PV/SC/snapshot fields.
- **Helm values live in the HelmRelease** in git. No `helm upgrade` by hand, no
  out-of-band manifests.
- **`targetNamespace` set via `ks.yaml` postBuild** (not `metadata.namespace`)
  is an intentional convention — do not flag or "fix" it.
- **App-level `ks.yaml` omit `interval`/`sourceRef`/`prune`/`timeout` on purpose.**
  `cluster-apps` injects them via `spec.patches` (selector
  `config.home-ops.io/managed=true`) at apply time. kubeconform flags these
  files as invalid — that is a false positive of the schema against this
  convention; do not "fix" by adding the fields.

## Sandboxing (ADR-03)

App workloads run `hostUsers: false` (user namespaces). AI workloads additionally
get an egress CiliumNetworkPolicy: LLM only via agentgateway lanes
(`complex`/`complex-raw`/`omni`/`micro`), MCP only via guarded `/mcp/{ro,rw,ext}`
tiers. Kata is removed — do not reintroduce runtimeClass references.

## App layout convention

```
kubernetes/apps/<namespace>/<app>/
├── ks.yaml                 # Flux Kustomization
└── app/
    ├── helmrelease.yaml    # app-template preferred; hostUsers: false
    ├── externalsecret.yaml # 1Password; no plaintext
    ├── ciliumnetworkpolicy.yaml
    └── httproute.yaml      # kgateway-internal + authentik forward-auth
```

No new conventions without an ADR in `docs/decisions/`.

## Verification (run before pushing)

- `prek run -a` — actionlint / zizmor / yamllint / kubeconform gates
- `just k8s render-ks <ns> <ks>` — render the kustomizations you touched;
  `just k8s apply-ks <ns> <ks>` applies with Flux's field-manager for local tests
- PR must go green: required check `Flux Checks - Success`

## PR conventions

- Conventional commits (`feat(scope):`, `fix(scope):`, `chore:`…), English only,
  terse — no essays in commit bodies or PR descriptions
- Third-party actions pinned by commit SHA with a version comment
- Workflows under `.github/workflows/` are CODEOWNERS-guarded

## More context

- Architecture decisions: `docs/decisions/*.md` (ADR-01 BGP/FRR, ADR-02 no public
  exposure, ADR-03 sandboxing)
- App inventory: `docs/application/`
- For omp sessions, operational rules: `.omp/skills/homelab-gitops`
