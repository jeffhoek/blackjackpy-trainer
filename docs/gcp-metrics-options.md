# GCP Metrics Options

The statsd integration (`blackjack/metrics.py`) is currently only wired into the console CLI path (`main.py`). The web server (`web/server.py`) has no metrics. Any GCP approach would also require adding metrics calls to the web session layer.

Cloud Run constraints that affect statsd:
- No sidecar containers (single container per instance)
- No inbound UDP (outbound UDP to a VPC endpoint works)
- Scale-to-zero instances make co-located receivers impractical

Cloud Run exports infrastructure metrics (request count, latency, instance count, CPU/memory) to Cloud Monitoring automatically with no code changes.

---

## Option 1 — External StatsD Receiver

Point `--statsd-host` at an external Telegraf instance on a GCE VM or internal VPC endpoint. Cloud Run makes outbound UDP calls to it. Telegraf forwards to InfluxDB; the existing `grafana/dashboard.json` works unchanged.

**Pros:** No code changes to `metrics.py`; same dashboard
**Cons:** Requires a GCE VM or always-on endpoint to manage; adds infrastructure cost

Steps:
1. Create a GCE VM in the same region/VPC
2. Install and configure Telegraf with `[[inputs.statsd]]` on UDP 8125
3. Configure VPC connector for Cloud Run → VM connectivity
4. Set `--statsd-host` to the VM's internal IP at deploy time

---

## Option 2 — Google Cloud Monitoring Custom Metrics

Replace `statsd.StatsClient` with the `google-cloud-monitoring` client library. Emit the same counters and gauges as Cloud Monitoring custom metrics under a `custom.googleapis.com/blackjack/` namespace.

**Pros:** No extra infrastructure; integrates with Cloud Monitoring dashboards and alerting
**Cons:** Requires rewriting `MetricsClient`; new dashboard (Grafana dashboard won't work)

Dependencies:
```
google-cloud-monitoring>=2.0
```

The `MetricsClient` interface (`card_dealt`, `answer`, `shoe_shuffled`, `end_session`) stays the same — only the backend changes.

---

## Option 3 — OpenTelemetry + Google Cloud OTLP

Use `opentelemetry-sdk` with the `opentelemetry-exporter-otlp-proto-grpc` and the Google Cloud OTLP exporter. Cloud Run has first-class OTLP support; metrics land in Cloud Monitoring automatically.

**Pros:** Standard, portable instrumentation; works across clouds
**Cons:** More dependencies; steeper setup than Option 2

Dependencies:
```
opentelemetry-sdk>=1.20
opentelemetry-exporter-gcp-monitoring>=1.0
```

---

## Option 4 — Prometheus `/metrics` Endpoint

Add a `/metrics` HTTP endpoint via `prometheus_client` to the FastAPI server. Use Google Cloud Managed Service for Prometheus (GMP) to scrape it from Cloud Run.

**Pros:** Prometheus ecosystem (existing tooling, PromQL); GMP is fully managed
**Cons:** Requires adding a metrics HTTP route to `web/server.py`; GMP scraping from Cloud Run requires configuration

Dependencies:
```
prometheus-client>=0.20
```

Expose via FastAPI:
```python
from prometheus_client import make_asgi_app
app.mount("/metrics", make_asgi_app())
```

---

## What Cloud Run Gives You for Free

No code required — visible immediately in Cloud Console → Cloud Run → service → Metrics tab:

| Metric | Source |
|--------|--------|
| Request count | Cloud Run |
| Request latency (p50/p95/p99) | Cloud Run |
| Active instances | Cloud Run |
| CPU / memory utilization | Cloud Run |
| WebSocket connection count | Derived from request metrics |
