# NFS StorageClass

- This folder manages NFS-based StorageClasses;
- backed by `csi-driver-nfs` PVC, supported by NAS;
- NFS path = `/shared-path/${pvc.metadata.name}`;
- Synology `MapAllToAdmin`, via `10.10.0.0/24` only;
