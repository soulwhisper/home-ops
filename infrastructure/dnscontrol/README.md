# DNSControl — Synology PowerDNS

`dnsconfig.js` manages `homelab.internal` and the internal view of `noirprime.com`.
Run DNSControl from a workstation on VLAN 100. ExternalDNS publishes Kubernetes
records to `noirprime.com`; `IGNORE_EXTERNAL_DNS("pdns-")` preserves its RRsets
and TXT ownership records.

### Before the first merge

On a Linux machine with the NAS SOPS age identity configured and a signed-in 1Password CLI with DevOps vault write access, import the **same** API key already encrypted for Doco-CD. Run once from the repo root if `DevOps/powerdns-api` does not exist. The key is piped directly to 1Password, not displayed or passed as a command argument.

```shell
(
  set -eo pipefail
  sops decrypt --input-type binary --output-type binary infrastructure/synology/powerdns/api-key.sops.conf \
    | jq -eRs 'capture("^api-key=(?<key>[0-9a-f]{64})\n$") |
        {title:"powerdns-api",category:"API_CREDENTIAL",
         fields:[{id:"credential",label:"credential",type:"CONCEALED",value:.key}]}' \
    | op item create --vault DevOps - >/dev/null
)
```

### Publish records

After Doco-CD starts PowerDNS, run from the repo root on VLAN 100. The API key
is sent over HTTP; use this endpoint only on the trusted LAN.

```shell
export PDNS_API_KEY=op://DevOps/powerdns-api/credential
cd infrastructure/dnscontrol

dnscontrol check
# First publish: create both zones and apply their static records.
op run -- dnscontrol push
```

For subsequent changes, preview and apply without creating any zones:

```shell
op run -- dnscontrol preview --no-populate
op run -- dnscontrol push --no-populate
```

See the [router cutover](../openwrt/README.md#adguard-home-dns-cutover) before
moving client queries. Update the private apex MX and SPF records when their
Cloudflare public counterparts change.

When rotating the API key, update the encrypted NAS config and the `credential` field together.
