# Edge router (ImmortalWrt)

Host-side configuration for the NTP/DNS/VPN edge, kept here for reference.
Nothing in this directory is applied by Flux; the router is configured by hand.

## AdGuard Home DNS cutover

Keep AdGuard Home as the recursive resolver for clients and Talos; Talos uses
`10.10.0.254`. A second `nameserver` in Talos is a fallback, not routing by
suffix. PowerDNS is authoritative only and cannot replace AdGuard for public
lookups.

1. Save a private backup of the running AdGuard Home configuration, including
   **Upstream DNS servers**, **DNS rewrites**, and **Custom filtering rules**.
   The matching rewrite answers are the baseline for the cutover.
2. After Doco-CD deploys PowerDNS, verify `docker logs powerdns-dnscontrol`
   shows a successful DNSControl run and the `externaldns-powerdns` deployment
   has synced. Compare the existing AdGuard `homelab.internal` and
   `noirprime.com` address rewrites with direct queries to `10.10.0.100`. Check
   all migrated names, including `k8s.homelab.internal` (three A records),
   `nas.homelab.internal`, `auth.noirprime.com`, and `postgres.noirprime.com`.
   Check both zone SOAs and the `noirprime.com` apex MX and TXT before switching.
3. In **Settings → DNS settings → Upstream DNS servers**, append the lines in
   [`adguardhome-powerdns-upstreams.txt`](adguardhome-powerdns-upstreams.txt).
   Keep the existing default upstreams. The `#` rule keeps the public ACME,
   DMARC, DKIM, and `opn` names on those upstreams; `derp.noirprime.com` keeps
   its local address in PowerDNS.
4. Remove the migrated `homelab.internal` and `derp.noirprime.com` DNS rewrites
   and the migrated `noirprime.com` ExternalDNS custom rules (including their
   `k8s-int.*` ownership TXT rules). Local rewrites take precedence over
   upstream forwarding. Do not remove unrelated rules. Clear the AdGuard cache.
5. Query AdGuard at `10.10.0.254` for both SOAs, the migrated records, a public
   exception such as `_dmarc.noirprime.com TXT`, and an unrelated name such as
   `registry.k8s.io`. If they regress, restore the saved AdGuard settings and
   clear the cache **before** rolling back the Git revision or stopping PowerDNS.

OpenWrt is configured by hand. Merging the Git revision changes the DNS
writers, not these settings or DHCP. Keep the old rewrites until the new
answers have been checked.

## chrony metrics

`chrony-metrics.cgi` serves the router's chrony state as Prometheus text. It
is installed as `/www/cgi-bin/chrony` (mode 0755) and scraped every 60 s by
`ScrapeConfig/chrony` in
`kubernetes/apps/monitoring-system/victoria-metrics/cluster/`.

```sh
scp infrastructure/openwrt/chrony-metrics.cgi root@10.10.0.254:/www/cgi-bin/chrony
ssh root@10.10.0.254 'chmod 755 /www/cgi-bin/chrony'
curl -s http://10.10.0.254/cgi-bin/chrony | head
```

`/www` is a tmpfs, so the file disappears on reboot or firmware upgrade;
reinstall it then. There is no cron: every vmagent scrape runs the CGI, so
each sample is fresh and timestamped by the scrape.

### Metrics

| Metric | Meaning |
| --- | --- |
| `chrony_system_offset_seconds` | current offset, system minus NTP; negative when the router is slow |
| `chrony_last_offset_seconds`, `chrony_rms_offset_seconds` | offset at the last update and its RMS |
| `chrony_frequency_ppm` | clock rate error; negative when the clock runs slow |
| `chrony_residual_frequency_ppm`, `chrony_skew_ppm` | remaining frequency error and its estimate |
| `chrony_root_delay_seconds`, `chrony_root_dispersion_seconds` | path delay and accumulated dispersion to the reference |
| `chrony_update_interval_seconds`, `chrony_stratum` | poll interval and served stratum |
| `chrony_source_offset_seconds{source}`, `chrony_source_frequency_ppm{source}`, `chrony_source_skew_ppm{source}`, `chrony_source_samples{source}` | per-upstream statistics |
| `chrony_source_reach{source}` | reachability register as decimal bits |
| `chrony_source_selected{source}` | 1 for the source chrony currently steers by |
| `chrony_sources_reachable` | count of sources with a non-zero reach bit |
| `chrony_metrics_ok` | 1 when every section parsed; 0 when `chronyc` or the parser failed |

### Why

Steps on this clock reach every production node (the prod Talos
`TimeSyncConfig` points at `10.10.0.254`. Without the router's own
offset, node and ceph clock alerts can only show that the source moved, not
which hop moved. The alerts are `RouterClockOffsetHigh` (above 50 ms),
`RouterClockSourcesUnreachable`, and `RouterClockMetricsUnavailable`.
