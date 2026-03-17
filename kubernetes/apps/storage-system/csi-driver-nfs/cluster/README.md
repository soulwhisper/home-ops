# NFS StorageClass

- This folder manages NFS-based StorageClasses;
- backed by `csi-driver-nfs` PVC, supported by NAS;
- NFS path = `/shared-path/${pvc.metadata.name}`;
- Synology MapAllToAdmin, `2000:2000`, fsGroup: `101`;
