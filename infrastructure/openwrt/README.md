# Edge router (ImmortalWrt)

Host-side configuration for the NTP/DNS/VPN edge, kept here for reference.
Nothing in this directory is applied by Flux; the router is configured by hand.

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

Steps on this clock reach every node (Talos `TimeSyncConfig` points at
`10.10.0.254`) and can trip ceph's `MON_CLOCK_SKEW`. Without the router's own
offset, node and ceph clock alerts can only show that the source moved, not
which hop moved. The alerts are `RouterClockOffsetHigh` (above 50 ms),
`RouterClockSourcesUnreachable`, and `RouterClockMetricsUnavailable`.
