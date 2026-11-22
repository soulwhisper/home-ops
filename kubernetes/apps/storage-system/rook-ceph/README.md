# rook-ceph

Operator (`app/`) + cluster (`cluster/`) + CSI drivers (`drivers/`).

## Ceph and CSI maintenance

`cluster/helmrelease.yaml` sets the Ceph daemon version.
`drivers/kustomization.yaml` supplies the CSI plugin image for both drivers
without changing their names or sidecars. The generated image-set name changes
with the image, so the CSI operator sees an `OperatorConfig` change and
reconciles both drivers.

Before merging an upgrade, verify a restore and confirm that the durable pools
are healthy. The cluster allows Rook to proceed past health checks. Do not
combine the storage window with a node drain or a database upgrade. Flux's
dependency order is operator → drivers → Ceph cluster; it does not prove that
the CSI data path works before Ceph rolls.

After reconciliation, check MONs, OSDs and durable PGs, then test RBD and CephFS
mounts and writes, RBD snapshot create/delete, and RGW reads and writes. Revert
the pins before reconciliation if the window is cancelled. If the rollout
stalls after any Ceph daemon has upgraded, do not treat an image revert as a
downgrade. Check the [cluster status and daemon pods](#troubleshooting-ceph-cli-access),
then read `kubectl -n storage-system logs deploy/rook-ceph-operator --since=15m`.
Use the [Rook Ceph troubleshooting guide](https://rook.io/docs/rook/v1.21/Troubleshooting/ceph-common-issues/#troubleshooting-techniques)
to diagnose the reported symptom before changing any daemons or data.

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
