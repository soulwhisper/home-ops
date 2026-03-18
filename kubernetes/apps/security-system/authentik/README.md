## Authentik

### Groups

- admin: allow all;
- internal: specific `media / smarthome / selfhosted / gaming` apps;
- external: invited only, usually for `gaming`;

### Users

- Created from Admin UI, disable registration;
- Password must be mixed, at least 16 chars;
- Keep deactivated users for auditing, no deletion;

### ForwardAuth

- add below files to ForwardAuth app

```yaml
---
apiVersion: gateway.kgateway.dev/v1alpha1
kind: TrafficPolicy
metadata:
  name: example-app-auth
spec:
  targetRefs:
    - group: gateway.networking.k8s.io
      kind: HTTPRoute
      name: example-app-route
  extAuth:
    extensionRef:
      name: authentik-ext-auth
      namespace: networking-system
```

```yaml
---
apiVersion: gateway.kgateway.dev/v1alpha1
kind: TrafficPolicy
metadata:
  name: example-api-no-auth
spec:
  targetRefs:
    - group: gateway.networking.k8s.io
      kind: HTTPRoute
      name: example-app-route
      sectionName: example-app-exception-rule
  extAuth:
    disable: {}
```

### OIDC

- app user mapping use `username` as identifier;
- create `client_id` and `client_secret` from UI;
- update these secrets to 1password;
- sync;
