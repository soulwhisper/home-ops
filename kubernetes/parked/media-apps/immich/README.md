## Immich

### System Integrity Checks

- [ref](https://docs.immich.app/administration/system-integrity/#folder-checks);
- run below commands via `browse-pvc` or nfs-server ssh;

```shell
kubectl browse-pvc photo -u 2000

# if via nfs-server ssh, change folders first

for dir in upload library thumbs encoded-video profile backups; do
    mkdir -p "$dir"
    touch -f "$dir/.immich"
done

```
