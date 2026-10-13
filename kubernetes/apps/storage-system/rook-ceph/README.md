# rook-ceph

Operator (`app/`) + cluster (`cluster/`) + CSI drivers (`drivers/`).

## Troubleshooting: ceph CLI access

The `kubectl rook-ceph` krew plugin can hang indefinitely (no timeout) when the
toolbox is disabled or the operator is mid-reconcile — observed 2026-10-13.
Don't wait on it; read the source of truth instead:

```bash
# Overall health + active ceph health details (what the operator sees):
kubectl -n storage-system get cephcluster -o jsonpath='{.items[0].status.ceph}'

# OSD/mon/mgr pod state and restarts:
kubectl -n storage-system get pods -l app=rook-ceph-osd

# Alert history for the window (vmalert Ceph* rules):
#   query ALERTS{alertname=~"Ceph.*"} over the window in vmsingle
```

`HEALTH_OK` in the CR status plus zero OSD restarts plus no Ceph* alerts is the
boring ground truth — trust it over any second-hand summary. If a real ceph CLI
is needed (osd df, radosgw-admin), retry `kubectl rook-ceph ...` later or check
whether the toolbox is enabled in the cluster HelmRelease.
