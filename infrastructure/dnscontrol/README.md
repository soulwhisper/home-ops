## DNS

- cloudflare action examples, check [ref](https://github.com/SukkaW/dnscontrol-gitops-template/tree/master);

```shell
brew install dnscontrol
dnscontrol [command]

docker run --rm -it -v "$(pwd):/dns" ghcr.io/stackexchange/dnscontrol [command]

pnpm install
pnpm run lint

dnscontrol write-types

# required: creds.json references $ADGUARD_PASSWORD (1Password item
# `app-user`, field `admin_pass` — same credentials external-dns uses)
export ADGUARD_PASSWORD="$(op read 'op://DevOps/app-user/admin_pass')"

dnscontrol check
dnscontrol preview
dnscontrol push
```

## Synology PowerDNS

`powerdns/` is a separate configuration. Running the commands above still targets only AdGuardHome.

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

### First publish and later changes

After Doco-CD brings HTTPS up, run from the repo root on the NAS management network:

```shell
export SSL_CERT_FILE="$PWD/kubernetes/apps/networking-system/externaldns/app/powerdns-api.pem"
export PDNS_API_KEY=op://DevOps/powerdns-api/credential
cd infrastructure/dnscontrol/powerdns

# First publish only: create both zones before previewing record changes.
op run -- dnscontrol create-domains
op run -- dnscontrol preview --no-populate
op run -- dnscontrol push --no-populate
```

For subsequent changes, run only `preview` and `push`. DNSControl owns the `pdns.homelab.internal` zone and the child zone's SOA/NS records; it ignores all A, AAAA, CNAME, and TXT records in the child. The dedicated ExternalDNS controller writes those records for `k8s.pdns.homelab.internal` only.

When rotating the API key, update the encrypted NAS config and the `credential` field together. For TLS renewal, replace the encrypted certificate/key bundle and the public certificate pin together. Do not disable certificate validation during rotation.
