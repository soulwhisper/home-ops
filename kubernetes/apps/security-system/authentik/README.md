## Authentik

### Groups

- admin: allow all;
- internal: specific `media / smarthome / selfhosted / servitor / gaming` apps;
- external: invited only, usually for `gaming`;

### Users

- Created from Admin UI, disable registration;
- Password must be mixed, at least 16 chars;
- Keep deactivated users for auditing, no deletion;

### Add a new ForwardAuth App

- 1. add `trafficpolicy.yaml` to app folder;
- 2. copy other app as template, change `provider name`, `application slug/name`, `meta_launch_url`, `policybinding`;
- 3. thats all.

### Add a new OIDC App

- 1. set OIDC es at app side;
- 2. copy other app as template, change `provider name`, `application slug/name`, `meta_launch_url`, `redirect_uris`, `policybinding`, `client_id`, `client_secret`;
- 3. add es name under authentik helmrelease `blueprints.secrets`;
- 4. thats all.

```shell
# how to create client_id and client_secret
APP="calibre"; \
CLIENT_ID="${APP}-$(openssl rand -hex 4)"; \
CLIENT_SECRET=$(openssl rand -hex 32); \
echo -e "ID:\t${CLIENT_ID}\nSecret:\t${CLIENT_SECRET}"

```
