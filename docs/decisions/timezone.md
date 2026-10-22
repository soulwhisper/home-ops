## ADR - 04 - Timezones: UTC by default, local time only where behavior requires it

**Context:**

The cluster previously ran `k8tz` as a cluster-wide admission webhook and
injected `Asia/Shanghai` into every pod outside `kube-system`. That default
created a recurring failure mode: vlagent parses offset-less klog timestamps
as UTC, so Go controllers logging in CST were stored up to eight hours in the
future (`VictoriaLogsFutureLogTimestamps`, homelab-tickets#27). Successive
fixes added per-workload `k8tz.io/timezone: UTC` annotations, but the default
kept reproducing the problem for new workloads.

`k8tz` annotations are also a poor ownership boundary: they are hidden
mutation, they apply per Pod rather than per container, they append a second
`TZ` instead of respecting the workload's own value, and the webhook remains a
cluster-wide `failurePolicy: Fail` dependency for pod creation.

**Decision:**

Remove `k8tz` entirely. Timezones are owned by workloads:

1. **UTC is the default.** Containers run with no injected `TZ`; images that
   do not declare one fall back to UTC.
2. **Local time is an explicit, narrow exception.** A workload gets
   `TZ=Asia/Shanghai` only when its behavior depends on local wall-clock time
   or when its user-facing output is rendered in local time.
3. **Schedules carry their own timezone.** Kubernetes CronJobs use
   `spec.timeZone`; APIs without a timezone field get a UTC cron expression.
4. **No k8tz annotations remain.** `k8tz.io/*` is not part of the operating
   model.

**Exceptions and rationale:**

| Workload | Timezone | Why |
|---|---|---|
| `immich` app container | `Asia/Shanghai` | Nightly job cron uses process local time; default `00:00` would otherwise run at 08:00 CST |
| `crafty-controller` | `Asia/Shanghai` | APScheduler uses `get_localzone()` for in-app schedules/backups |
| `moviepilot` | `Asia/Shanghai` | Scheduler reads `TZ` into `settings.TZ`; the image also defaults to CST |
| `trendradar` | `Asia/Shanghai` | Explicit daily `05:00` crawl; logs carry a `+08:00` offset |
| `robusta-runner` | `Asia/Shanghai` | Ticket `Started`/`Ended` fields are user-facing presentation |
| `robusta-operator` | `UTC` | `ScheduledHealthCheck` has no timezone field; its cron expressions are UTC |
| `cnpg-operator` | `UTC` | `ScheduledBackup` has no timezone field; its cron expression is UTC |
| `postgres-backup-verify` CronJob | `timeZone: Asia/Shanghai` | Preserve the Sunday 04:00 local verification slot |
| Kopiur schedules | `Asia/Shanghai` | `ClusterRepository.spec.scheduleDefaults.timezone` is already explicit |
| system-upgrade-controller Plans | `Asia/Shanghai` | Plan resources already declare their schedule timezone |

Applications that expose browser-local timestamps or have their own timezone
setting do **not** get process `TZ`: Grafana, Headlamp, Homepage, Authentik,
Frigate, Navidrome, Kavita, MeTube, Stirling PDF, Karakeep, SearXNG, Hindsight,
Firecrawl, Langfuse, FoundryVTT, and Scrypted render in the browser or in
application/user settings.

Netbox (`TIME_ZONE`) and Home Assistant (`time_zone`) keep application-level
timezones independently of the process timezone. MoviePilot reads `TZ` into
`settings.TZ`, which is why it gets an explicit environment variable.
`kube-system` was already outside k8tz's injection scope and remains UTC.

**Consequences:**

- Infra logs default to UTC, matching vlagent's klog parser assumption; the
  future-timestamp alert should remain clear without per-workload annotations.
- Removing the webhook removes a cluster-wide pod-admission dependency and the
  extra init container/zoneinfo mounts from every pod.
- Existing pods keep their injected `TZ` and mounts until they are recreated;
  the change does not rewrite running pods.
- Old CST klog rows can remain future-dated until they age out; they cannot be
  selectively deleted.
- Images that provide `TZ=Asia/Shanghai` explicitly keep it; this is deliberate
  for MoviePilot and the SGCC bridge.
- A workload that needs local time but lacks tzdata must add a zoneinfo mount or
  keep its own `TZ` dependencies; the k8tz bootstrap is gone.

**Verification:**

- `vl_storage_log_max_timestamp_seconds - time()` stays below 1800.
- `date` in every exception pod reports CST; all other workload pods report UTC.
- `kubectl get cronjob -A -o custom-columns=...` shows the expected `timeZone`.
- `kubectl get mutatingwebhookconfiguration k8tz` returns NotFound.
- `ScheduledHealthCheck` next runs remain at the same wall-clock times after the
  UTC cron conversion.

**Rollback:**

Revert this change to restore the previous manifests. No data migration is
involved; pods pick up the previous timezone configuration on their next
recreation. Reinstalling `k8tz` would also restore webhook injection.
