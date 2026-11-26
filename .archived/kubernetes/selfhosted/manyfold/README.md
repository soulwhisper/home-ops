# Archived Manyfold

The model library is on the NAS at `/volume1/3d-assets/library`. The archived
`selfhosted-nfs` definition supplied its NFS claim. The NFS StorageClass keeps
this directory when its claim and binding are removed. A standalone NAS
deployment can bind that directory to `/libraries/main` without recreating a
Kubernetes claim.

The `/config` PVC contains separate application state, including the database.
Preserve a recoverable copy before pruning `selfhosted-apps/manyfold`; the
Ceph StorageClass deletes the backing volume. A copy of the model library is
not a backup of this state.

To restore on Kubernetes, reselect both definitions and `kopiur/shared` in the
`selfhosted-apps` index. Restore the forward-auth blueprint and its outpost
provider binding, plus the icon and its entry in the cluster Homepage
generator. Recover `/config` separately. If the database is new, [register the
library](https://manyfold.app/sysadmin/advanced_tasks.html) after the pod starts:

```sh
kubectl -n selfhosted-apps exec deploy/manyfold -- \
  bundle exec /usr/src/app/bin/manyfold libraries create \
    --name=main --path=/libraries/main
```
