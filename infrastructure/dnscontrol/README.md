# DNSControl — Synology PowerDNS

`dnsconfig.js` manages `homelab.internal` and the internal view of `noirprime.com`.
Doco-CD runs the `dnscontrol` service on the NAS to create the zones and apply
this configuration before publishing the HTTPS API. ExternalDNS then publishes
Kubernetes records to `noirprime.com`; `IGNORE_EXTERNAL_DNS("pdns-")` keeps their
RRsets and TXT ownership records out of DNSControl's changes.

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

### Preview a change

From the repo root on VLAN 100, after the API is up:

```shell
export SSL_CERT_FILE="$PWD/kubernetes/apps/networking-system/externaldns/app/powerdns-api.pem"
export PDNS_API_URL=https://10.10.0.100:8443
export PDNS_API_KEY=op://DevOps/powerdns-api/credential
cd infrastructure/dnscontrol

dnscontrol check
op run -- dnscontrol preview --no-populate
```

Publish by merging the record changes; use `docker logs powerdns-dnscontrol`
on the NAS to verify the run. See the [router cutover](../openwrt/README.md#adguard-home-dns-cutover)
before moving client queries. Update the private apex MX and SPF records here
when their Cloudflare public counterparts change.

When rotating the API key, update the encrypted NAS config and the `credential` field together. For TLS renewal, replace the encrypted certificate/key bundle and the public certificate pin together. Do not disable certificate validation during rotation.
