## MCP Federation

### Add a new MCP server

- 1. copy other app as template;
- 2. edit `federation/app/agentgatewaybackend.yaml`, add new item under `spec.mcp.targets`;

```yaml
- name: example # tools prefix
  selector:
    services:
      matchLabels:
        app.kubernetes.io/name: example-app # app label
```

- 3. thats all.
