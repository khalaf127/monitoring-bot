# monitoring-bot

A pizza ordering system used as the target for an incident game: things break, players fix them, and a Discord bot keeps score.

## Project status

**Done**
1. Pizza shop services with Prometheus metrics, plus a load generator for constant traffic.
2. Grafana dashboards: *Pizza Shop* (orders, errors, latency, payments, firing alerts) and *Node Exporter Full* (host).
3. Alerting: recording rules, alert rules with `promtool` unit tests, Alertmanager with grouping and inhibition, and runbooks in [docs/runbooks.md](docs/runbooks.md).

**Current step: Discord bot (not started)**
- Alertmanager has no receiver yet. Alerts only show in the Alertmanager UI and Grafana.
- The bot needs an HTTP endpoint (e.g. `POST /alerts`) that receives Alertmanager webhooks, including `resolved` ones.
- Then add it as a receiver in `monitoring/alertmanager/alertmanager.yml` (example commented there) and as a service in `docker-compose.yml`.
- Game idea: when an alert resolves, credit the player who fixed it based on time to fix.

**Later**
- The incident game itself: a way to trigger chaos (the chaos knobs below) and keep score.
- Disable Grafana anonymous admin access before deploying anywhere non-local.

## Services

| Service | Role | Chaos knobs |
|---|---|---|
| order-api | Takes orders, stores them in Postgres, calls payment then kitchen | |
| payment-service | Accepts or declines payments | `FAILURE_RATE`, `LATENCY_MS` |
| kitchen-service | "Cooks" pizzas | `COOK_MIN_MS`, `COOK_MAX_MS` |
| load-generator | Sends random orders like real customers | `ORDERS_PER_SECOND` (default 2) |
| postgres | Stores orders | |

Every app service exposes `/health` and `/metrics` (Prometheus).

## Monitoring stack

| Component | What it does | URL |
|---|---|---|
| Prometheus | Scrapes metrics every 5s, evaluates recording and alert rules | http://localhost:9090 |
| Alertmanager | Groups, deduplicates and routes firing alerts | http://localhost:9093 |
| Grafana | Dashboards (*Pizza Shop*, *Node Exporter Full*) and alert view | http://localhost:3000 |
| node-exporter | Host CPU, memory, disk, network | |
| postgres-exporter | Database health (`pg_up`) | |

How an alert flows:

```
services /metrics ──scrape──▶ Prometheus ──rules──▶ alert firing ──▶ Alertmanager ──▶ receiver (Discord bot, later)
                                   │                                     │
                                   └────────────── Grafana ◀─────────────┘
```

### Alerts

Defined in `monitoring/prometheus/rules/alerts.yml`. Each one links to a section of [docs/runbooks.md](docs/runbooks.md).

| Alert | Severity | Fires when |
|---|---|---|
| TargetDown | critical | a scrape target is down for 1m |
| PostgresDown | critical | the database is unreachable for 1m |
| HighErrorRate | critical | >5% of a service's requests return 5xx for 2m |
| NoPizzasServed | critical | no order reached `ready` for 5m |
| HighLatency | warning | a service's p95 latency is >2s for 5m |
| PaymentDeclineRateHigh | warning | >20% of payments declined for 5m |
| HostHighCpu / HostLowMemory / HostDiskAlmostFull | warning | host resources run low |

Alertmanager mutes knock-on alerts: when a service is down, its error/latency alerts are suppressed.

## Run locally

```bash
docker compose up -d --build
```

The load generator starts sending orders right away. To place one by hand:

```bash
curl -X POST localhost:8081/orders -H 'content-type: application/json' -d '{"pizza":"margherita"}'
```

Order API docs: http://localhost:8081/docs

### Try an incident

```bash
docker compose stop kitchen-service   # TargetDown after ~1m, HighErrorRate on order-api after ~2m
docker compose start kitchen-service  # alerts resolve
```

Watch it in Grafana (*Pizza Shop* → *Firing alerts*) or at http://localhost:9093.

### Change rules

Edit files in `monitoring/prometheus/rules/`, then test and reload without restarting:

```bash
docker run --rm -v ./monitoring/prometheus:/p -w /p --entrypoint promtool prom/prometheus:v3.0.1 test rules tests/alerts_test.yml
curl -X POST localhost:9090/-/reload
```
