# Frigate alerts → hermes-agent (parked)

Frigate, frigate-vision and the smarthome namespace are parked. This note
records the integration contract so it can be restored without re-deriving it.

## Flow

1. Frigate runs its native GenAI description (`objects.genai`) against the
   agentgateway `omni` lane. The prompt makes the description start with
   `[low|medium|high]`.
2. `frigate-vision` subscribes to `frigate/tracked_object_update` over MQTT.
   For `type: description` events it parses the severity prefix, drops events
   below `MIN_SEVERITY` (default `medium`), enriches via
   `GET /api/events/<id>` and posts a signed alert to hermes.
3. Hermes accepts the alert on its `ops` profile webhook route
   (`/p/ops/webhooks/frigate-alert`) and logs it (`deliver: log`).

## Hermes side (removed while parked)

`kubernetes/apps/servitor-apps/hermes-agent/app/configmap.yaml` carried:

```yaml
platforms:
  webhook:
    enabled: true
    extra:
      port: 8644
      routes:
        frigate-alert:
          # double $ survives Flux postBuild substitution
          secret: $${FRIGATE_WEBHOOK_SECRET}
          profile: ops
          prompt: |
            [Frigate alert] camera={camera} severity={severity}: {description}
            (label={label}, zones={zones}, event={event_id}, ts={timestamp})
          deliver: log
```

`FRIGATE_WEBHOOK_SECRET` came from the hermes ExternalSecret, mapping
1Password `hermes-agent` `webhook_secret_frigate`.

## Wire protocol

- `POST http://hermes-agent.servitor-apps.svc.cluster.local:8644/p/ops/webhooks/frigate-alert`
- Signature: hex HMAC-SHA256 over `"<timestamp>." + body` with the shared
  secret.
- Headers: `X-Webhook-Signature-V2: <hex>`, `X-Webhook-Timestamp: <unix>`,
  `Content-Type: application/json`.
- Body:

```json
{
  "event_type": "frigate.alert",
  "event_id": "...",
  "camera": "...",
  "label": "...",
  "zones": ["..."],
  "severity": "low|medium|high",
  "description": "...",
  "timestamp": 0
}
```

The sender is `frigate-vision`; its `HERMES_WEBHOOK_URL` and
`HERMES_WEBHOOK_SECRET` must point at the same route and secret value.

## Resume checklist

1. Unpark `smarthome-apps` (frigate, frigate-vision, mosquitto and the rest).
2. Re-add the `frigate-alert` webhook route above to hermes, restore
   `FRIGATE_WEBHOOK_SECRET` in the hermes ExternalSecret, and re-add
   `FRIGATE_WEBHOOK_SECRET=$${FRIGATE_WEBHOOK_SECRET}` to the seed script's
   ops `.env` heredoc. The ExternalSecret alone does not reach the runtime
   profile.
3. Allow TCP 8644 from the sender. Pod IPs are in `10.100.0.0/17`, so the
   existing `10.10.0.0/24` LAN rule does not cover them. Add an ingress rule
   selecting the `frigate-vision` pod in `smarthome-apps` (the previous rule
   selected `app.kubernetes.io/name: frigate`, which is not the forwarder).
4. Set `HERMES_WEBHOOK_URL` / `HERMES_WEBHOOK_SECRET` in `frigate-vision`
   (same secret as hermes), and keep `MIN_SEVERITY` at the intended level.
5. Rotate the shared secret on both sides together; a mismatch fails the
   signature check at hermes.
