## Volsync

- This is a method to backup snapshots to NFS;

### Components

- `cnpg:cronjob`
- `volsync:nfs`

### MutatingAdmissionPolicy

- `kubernetes/apps/storage-system/volsync/app/policy`
- `talconfig.yaml`

```yaml
# controlPlane only patches
patches:
  # : ApiServer configuration
  # :: Enable MutatingAdmissionPolicy;
  - |-
    cluster:
      apiServer:
        extraArgs:
          runtime-config: admissionregistration.k8s.io/v1alpha1=true
          feature-gates: MutatingAdmissionPolicy=true
```

### Talos NFS mount

```yaml
# talconfig.yaml, general patches
patches:
  # : Configure NFS mount options
  - |
    machine:
      files:
        - op: overwrite
          path: /etc/nfsmount.conf
          permissions: 0o644
          content: |
            [ NFSMount_Global_Options ]
            nfsvers=4.1
            hard=True
            noatime=True
            nconnect=16

# helmrelease.yaml, example persistence
    persistence:
      shared:
        type: nfs
        server: nas.homelab.internal
        path: /mnt/Arcanum/Media
        globalMounts:
          - path: /data/nas-media/Downloads/qbittorrent
            subPath: Downloads/qbittorrent
```
