# Smart-home MCP tier

This bundle holds the `MCPGroup smarthome` and the `mcp-home-assistant` server
for the smart-home namespace, archived with that stack. Flux does not render it,
so neither object exists in the cluster.

Restoring requires all of the following, in order:

1. Restore the smart-home applications under `kubernetes/apps/smarthome-apps/`
   and re-add their entries to the namespace index so the Home Assistant
   endpoint exists.
2. Copy this directory to `kubernetes/apps/servitor-apps/mcp/smarthome/` and add
   `./smarthome/ks.yaml` to the active MCP index.
3. Add the serving path: a `VirtualMCPServer smarthome`, its agentgateway
   backend/route/policy, and a dedicated `mcp_smarthome` key (plus the guardrail
   choice) before issuing a credential.
