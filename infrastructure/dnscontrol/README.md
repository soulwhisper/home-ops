# DNSControl — Synology PowerDNS

`dnsconfig.js` manages `homelab.internal` and the internal view of `noirprime.com`.
Run DNSControl from a workstation on VLAN 100. ExternalDNS publishes Kubernetes
records to `noirprime.com`; `IGNORE_EXTERNAL_DNS("pdns-")` preserves its RRsets
and TXT ownership records.

### Before the first merge

Set `DevOps/dns-keys/powerdns` in 1Password to the same value as `api-key` in
[`api-key.sops.conf`](../synology/powerdns/api-key.sops.conf). DNSControl and
ExternalDNS both read that field. Update both copies when rotating the key.

### Publish records

After Doco-CD starts PowerDNS, run from the repo root on VLAN 100. The API key
is sent over HTTP; use this endpoint only on the trusted LAN.

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

### Editor type hints

Run `dnscontrol write-types` in `infrastructure/dnscontrol` to generate
`types-dnscontrol.d.ts` for the editor's JavaScript checks.
