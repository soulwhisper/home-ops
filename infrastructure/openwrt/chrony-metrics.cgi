#!/bin/sh
# Prometheus text for the edge router's chrony, scraped by vmagent.
# Install on the router as /www/cgi-bin/chrony (0755); see README.md.

set -u

printf 'Content-Type: text/plain; version=0.0.4; charset=utf-8\n\n'

fail() {
  printf 'chrony_metrics_ok 0\n'
  exit 0
}

CHRONYC=/usr/bin/chronyc
if [ ! -x "$CHRONYC" ]; then
  CHRONYC=$(command -v chronyc 2>/dev/null) || fail
fi

tracking=$("$CHRONYC" tracking 2>/dev/null) || fail
[ -n "$tracking" ] || fail

printf '%s\n' "$tracking" | awk '
  /^Stratum/         { printf "chrony_stratum %d\n", $3; seen = 1 }
  /^System time/     { v = $4 + 0; if ($6 == "slow") v = -v; printf "chrony_system_offset_seconds %.9g\n", v }
  /^Last offset/     { printf "chrony_last_offset_seconds %.9g\n", $4 + 0 }
  /^RMS offset/      { printf "chrony_rms_offset_seconds %.9g\n", $4 + 0 }
  /^Frequency/       { v = $3 + 0; if ($5 == "slow") v = -v; printf "chrony_frequency_ppm %.9g\n", v }
  /^Residual freq/   { printf "chrony_residual_frequency_ppm %.9g\n", $4 + 0 }
  /^Skew/            { printf "chrony_skew_ppm %.9g\n", $3 + 0 }
  /^Root delay/      { printf "chrony_root_delay_seconds %.9g\n", $4 + 0 }
  /^Root dispersion/ { printf "chrony_root_dispersion_seconds %.9g\n", $4 + 0 }
  /^Update interval/ { printf "chrony_update_interval_seconds %.9g\n", $4 + 0 }
  END { if (!seen) exit 1 }
' || fail

sources=$("$CHRONYC" sources 2>/dev/null) || sources=
stats=$("$CHRONYC" sourcestats 2>/dev/null) || stats=

if [ -n "$sources" ]; then
  printf '%s\n' "$sources" | awk '
    function octal(v,   i, r) {
      r = 0
      for (i = 1; i <= length(v); i++) r = r * 8 + substr(v, i, 1)
      return r
    }
    $1 ~ /^[\^=#]/ && length($1) == 2 {
      reach = octal($5)
      printf "chrony_source_reach{source=\"%s\"} %d\n", $2, reach
      if (substr($1, 2, 1) == "*") printf "chrony_source_selected{source=\"%s\"} 1\n", $2
      if (reach != 0) up++
    }
    END { printf "chrony_sources_reachable %d\n", up + 0 }
  '
fi

if [ -n "$stats" ]; then
  printf '%s\n' "$stats" | awk '
    function secs(v,   u) {
      u = v
      sub(/^[+-]?[0-9.]+/, "", u)
      v = v + 0
      if (u == "ms") return v / 1000
      if (u == "us") return v / 1000000
      return v
    }
    $2 ~ /^[0-9]+$/ && $1 ~ /[0-9]/ {
      printf "chrony_source_offset_seconds{source=\"%s\"} %s\n", $1, secs($7)
      printf "chrony_source_frequency_ppm{source=\"%s\"} %s\n", $1, $5 + 0
      printf "chrony_source_skew_ppm{source=\"%s\"} %s\n", $1, $6 + 0
      printf "chrony_source_samples{source=\"%s\"} %d\n", $1, $2
    }
  '
fi

printf 'chrony_metrics_ok 1\n'
