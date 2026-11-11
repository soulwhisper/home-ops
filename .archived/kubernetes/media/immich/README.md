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

### CNPG declarations for restore

The active `postgres` Cluster does not declare the `immich` role or `Database`.
Add both before restoring so ownership and the required extensions stay
declarative. Restore Immich in pgvector mode (`DB_VECTOR_EXTENSION: pgvector`,
already set in the archived HelmRelease). The image must provide `pgvector` and
`earthdistance`; `earthdistance` depends on `cube`, which is declared
separately because the CNPG `Database` controller issues a plain
`CREATE EXTENSION` (no `CASCADE`). Neither the image nor CNPG installs a missing
extension package. The image no longer ships `vchord`, so VectorChord mode is
not an option for this restore.

The app's `init-db` container can provision the role and database from the
superuser secret; the `Database` declaration is what ensures the pgvector-mode
extensions.

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
