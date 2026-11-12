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
already set in the archived HelmRelease). The image must provide `pgvector`;
Immich's own migrations create the remaining extensions they require when run
with the documented superuser/owner setup. Verify `pg_available_extensions` in
the target database before restore. Do not add the standard contrib extensions
to the `pig ext install` package list or reinstall them to match this note;
re-installing can drift the shipped versions. The replacement image drops
`vchord`, while the currently pinned image still contains it;
`DB_VECTOR_EXTENSION=pgvector` keeps this restore on pgvector either way.

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

### Renovate configuration for restore

Four entries were removed from `.renovate/` when this app was archived; restore
them or the images stop being tracked (Renovate ignores `.archived/**`, so
nothing else re-adds them):

1. `.renovate/groups.json5` — the `Immich` group:

   ```json5
   {
     description: "Immich Group (server and machine-learning resolve via GitHub releases)",
     groupName: "Immich",
     matchDatasources: ["docker", "github-releases", "custom.immich-machine-learning"],
     matchPackageNames: ["/immich-server/", "/immich-machine-learning/", "immich-app/immich"],
     group: { commitMessageTopic: "{{{groupName}}} group" },
     minimumGroupSize: 1,
   }
   ```

2. `.renovate/packageRules.json5` — the two lookup overrides (`immich-server`
   via `github-releases` because its tag list is 31k+ entries; `immich-machine-learning`
   via the custom datasource because its tags carry a `-openvino` suffix).

3. `.renovate/custom.json5` — the `immich-machine-learning` custom datasource
   (GitHub releases → `<tag>-openvino`).

4. `.renovate/packageRules.json5` — `prodrigestivill/postgres-backup-local` in
   the "Pin Postgres version to 18" pattern list. This app's HelmRelease is the
   only archived user of that image; re-add it with the app or the sidecar stops
   getting pinned to 18.
