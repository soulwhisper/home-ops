# .archived/woodpecker

Woodpecker CI, retired 2026-10-06. GitHub Actions owns PR verification;
agent workflows run there via the tailnet pass-through. The three data-plane
crons (dr-test, image-warm, postgres-backup-verify) died with the app —
re-introduce as Kubernetes CronJobs if missed.

- `k8s/` — former `kubernetes/apps/worker-apps/woodpecker` Flux app
  (HelmRelease + OAuth to NAS Forgejo)
- `parent-kustomization.yaml` — former `worker-apps` namespace kustomization

Not applied to the cluster. Nothing here is live.
