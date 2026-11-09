# Parked smarthome MCP tier

This bundle holds the `MCPGroup smarthome` and the `mcp-home-assistant`
server for the parked `smarthome-apps` namespace. It is not rendered by
`apps/servitor-apps/mcp/kustomization.yaml`, so neither object exists in the
cluster while parked.

Resuming requires all of the following, in order:

1. Unpark `smarthome-apps` (move it back under `kubernetes/apps/` and re-add
   its index) so the Home Assistant endpoint exists.
2. Move this directory to `kubernetes/apps/servitor-apps/mcp/smarthome/` and
   add `./smarthome/ks.yaml` to the active MCP index.
3. Re-create the serving path that deliberately is not parked here: an
   `MCPGroup smarthome` is created by `kustomization.yaml`, but a
   `VirtualMCPServer smarthome`, its agentgateway backend/route/policy, and a
   dedicated `mcp_smarthome` key do not exist. Add them (plus the guardrail
   choice) before issuing a credential.
