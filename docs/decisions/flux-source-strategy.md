## ADR - 05 - Flux: keep one Git source for Kustomizations

**Context:**

The root, application index, and application Kustomizations read the same
`GitRepository` within the cluster. Flux can also split a Git source into
content-addressed artifacts. Upstream home-ops [PR #12208] enables
`source-watcher`; [PR #12207] uses it to publish one `ExternalArtifact` per
application directory. A change confined to one directory no longer triggers
other application Kustomizations through a source revision change. Periodic
reconciliation still runs, and changes to files copied into every artifact
can still trigger all consumers.

**Decision:**

Keep application Kustomizations on the cluster's shared `GitRepository`.
Do not enable `source-watcher` or migrate to per-application artifacts for
this optimization. Helm chart sources are unchanged.

**Rationale & Comparison:**

1. **Keep the revision check across application boundaries.** A Flux
   `dependsOn` reference can cross namespaces. With the default readiness
   check, Flux also verifies that the dependency has applied the current
   source revision when both Kustomizations reference the same source. The
   [controller checks the source kind, name, and namespace][dependency check],
   not the commit from which different artifacts were generated. With separate
   artifacts, a dependency can still be Ready at an older revision when a
   dependent starts applying. A change that upgrades a CRD and adds a field
   to a dependent resource can therefore reach the old schema first. A shorter
   retry interval helps after a failed apply; it does not restore ordering.
   Artifacts also need to explicitly include any shared files referenced by
   their consumers; cross-namespace references do not make those files
   available inside a different artifact.
2. **Keep one revision to follow during reconciliation.** With a shared Git
   source, an applied Kustomization revision can be compared directly with
   the Git revision. Per-application artifacts add a generation and publication
   step. The applied revision identifies the artifact content; the Git origin
   is [separate metadata][artifact revision]. Diagnosis and rollback then
   require checking which content was published and which content the consumer
   applied. A generator or artifact-serving failure can stall reconciliation
   even while Git is healthy, without immediately stopping existing workloads.

**Trade-off:**

An unrelated Git commit can still enqueue Kustomizations whose manifests did
not change. The shared revision check is not an atomic rollout and only gates
explicit dependencies. Revisit artifact splitting if measurements show that
Git-triggered reconciliation is causing sustained API pressure or longer
rollouts, and test a low-risk application before moving shared dependencies.

[PR #12208]: https://github.com/onedr0p/home-ops/pull/12208
[PR #12207]: https://github.com/onedr0p/home-ops/pull/12207
[dependency check]: https://github.com/fluxcd/kustomize-controller/blob/v1.10.2/internal/controller/kustomization_controller.go#L590-L665
[artifact revision]: https://fluxcd.io/flux/components/source/artifactgenerators/#artifacts
