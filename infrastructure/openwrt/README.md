# Edge router integrations

## AdGuard Home upstreams

Use these entries under **Upstream DNS servers**. PowerDNS at `10.10.0.100`
serves `homelab.internal` and the private view of `noirprime.com`. The more
specific `#` rule uses AdGuard Home's default upstreams for public records.

```text
[/homelab.internal/noirprime.com/]10.10.0.100
[/_acme-challenge.noirprime.com/_dmarc.noirprime.com/_domainkey.noirprime.com/opn.noirprime.com/]#
```

## Router NTP metrics

`chrony-metrics.cgi` exposes the homelab's NTP source to VictoriaMetrics.
`ScrapeConfig/chrony` in
[`victoria-metrics/cluster`](../../kubernetes/apps/monitoring-system/victoria-metrics/cluster/)
scrapes `http://10.10.0.254/cgi-bin/chrony` every 60 seconds.

```sh
scp infrastructure/openwrt/chrony-metrics.cgi root@10.10.0.254:/www/cgi-bin/chrony
ssh root@10.10.0.254 'chmod 755 /www/cgi-bin/chrony'
curl -s http://10.10.0.254/cgi-bin/chrony | head
```

The CGI survives normal reboots. Reinstall it after a firmware upgrade if the
upgrade did not preserve `/www/cgi-bin/chrony`.

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
| `chrony_metrics_ok` | 0 on a detected `chronyc` or tracking parse failure; 1 otherwise |

### Why

Production Talos nodes share this NTP source. The router's offset and source
reachability help distinguish a shared clock problem from drift on one node.
See `RouterClockOffsetHigh`, `RouterClockSourcesUnreachable`, and
`RouterClockMetricsUnavailable` in the monitoring rules.
