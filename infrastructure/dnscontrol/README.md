# DNSControl — Synology PowerDNS

`dnsconfig.js` manages `homelab.internal` and the internal view of `noirprime.com`.
Run DNSControl from a workstation on VLAN 100. ExternalDNS publishes Kubernetes
records to `noirprime.com`; `IGNORE_EXTERNAL_DNS("k8s-int.")` preserves its RRsets
and TXT ownership records.

## Publish records

After Doco-CD starts PowerDNS, run from the repo root on VLAN 100. The NAS
binds the API directly to its LAN IP so PowerDNS can enforce the VLAN 100
source ACL. DNSControl and ExternalDNS use the same 1Password field, which must
match `api-key` in [`powerdns.sops.conf`](../synology/powerdns/powerdns.sops.conf).
The API key is sent over HTTP; use this endpoint only on the trusted LAN.

```shell
export PDNS_API_KEY=op://DevOps/dns-keys/powerdns
cd infrastructure/dnscontrol

dnscontrol check

# First publish, create both zones and apply their static records.
op run -- dnscontrol push

# For subsequent changes, preview and apply without creating any zones.
op run -- dnscontrol preview --no-populate
op run -- dnscontrol push --no-populate
```

Update the private apex MX and SPF records when their
Cloudflare public counterparts change.

## Editor type hints

Run `dnscontrol write-types` in `infrastructure/dnscontrol` to generate
`types-dnscontrol.d.ts` for the editor's JavaScript checks.
