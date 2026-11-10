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

### CNPG declarations for unparking

Parking removed the `immich` role and `Database` declarations from
`cnpg-operator/cluster/postgres.yaml`. Re-add both before unparking so ownership
and the required extensions stay declarative. The app's `init-db` container can
provision the role and database from the superuser secret; the `Database`
declaration is what ensures `vector`, `vchord`, `cube`, and `earthdistance`.

Role (inside the `postgres` Cluster `spec.managed.roles`):

```yaml
      - name: immich
        ensure: present
        login: true
        superuser: false
```

Database:

```yaml
---
apiVersion: postgresql.cnpg.io/v1
kind: Database
metadata:
  name: immich
spec:
  cluster:
    name: postgres
  name: immich
  owner: immich
  extensions:
    - name: vector
      ensure: present
    - name: vchord
      ensure: present
    - name: cube
      ensure: present
    - name: earthdistance
      ensure: present
```

These declarations recreate an empty database and role only. They do not
recover data: the `immich` database is absent on all three instances, so
contents must come from a CNPG/Barman base backup and WAL archive predating the
DROP, restored to a target time before it; finish that restore before starting
Immich.
