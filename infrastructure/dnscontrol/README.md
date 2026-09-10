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
