# monitoring-bot

A pizza ordering system used as the target for an incident game: things break, players fix them, and a Discord bot keeps score.

## Services

| Service | Role | Chaos knobs |
|---|---|---|
| order-api | Takes orders, stores them in Postgres, calls payment then kitchen | |
| payment-service | Accepts or declines payments | `FAILURE_RATE`, `LATENCY_MS` |
| kitchen-service | "Cooks" pizzas | `COOK_MIN_MS`, `COOK_MAX_MS` |

Every service exposes `/health` and `/metrics` (Prometheus).

## Run locally

```bash
docker compose up -d --build
curl -X POST localhost:8081/orders -H 'content-type: application/json' -d '{"pizza":"margherita"}'
```

- Order API: http://localhost:8081/docs
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000
