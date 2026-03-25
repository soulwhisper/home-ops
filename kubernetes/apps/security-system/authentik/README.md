## Authentik

### Groups

- admin: allow all;
- internal: specific `media / smarthome / selfhosted / gaming` apps;
- external: invited only, usually for `gaming`;

### Users

- Created from Admin UI, disable registration;
- Password must be mixed, at least 16 chars;
- Keep deactivated users for auditing, no deletion;

### Add a new ForwardAuth App

- 1. add `trafficpolicy.yaml` to app folder;
- 2. copy other app as template, change `provider name`, `application slug/name`, `meta_launch_url`, `policybinding`;
- 3. add provider to `app/blueprints/core/outpost-proxy.yaml`, under providers list;
- 4. thats all.

### Add a new OIDC App

- 1. set OIDC settings at app side;
- 2. copy other app as template, change `provider name`, `application slug/name`, `meta_launch_url`, `redirect_uris`, `policybinding`;
- 3. add ip slug into `infrastructure/terraform/authentik/apps.txt`;
- 4. apply terraform at least once;
- 5. sync 1password secrets in the cluster;
- 6. thats all.
