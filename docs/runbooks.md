# Runbooks

Every alert links here through its `runbook_url`. A runbook answers: what does this alert mean, how do I confirm it, and what do I try first.

## TargetDown

**Meaning:** Prometheus can't scrape a service's `/metrics`. The container is stopped, crashed, or hung.

**Check:**
```bash
docker compose ps
docker compose logs --tail=50 <service>
```
**Fix:** `docker compose up -d <service>`. If it keeps crashing, read the logs for the cause before restarting again.

## PostgresDown

**Meaning:** postgres-exporter is up but can't connect to the database. order-api will fail every order.

**Check:** `docker compose ps postgres` and `docker compose logs --tail=50 postgres`. A full disk is a common cause.
**Fix:** `docker compose up -d postgres`, then confirm `pg_up` is 1 in Prometheus.

## HighErrorRate

**Meaning:** More than 5% of a service's requests return 5xx.

**Check:** On the Pizza Shop dashboard, look at *Orders per second* by status:
- `kitchen_failed` → kitchen-service is down or erroring
- `payment_unreachable` → payment-service is down
- errors with no status change → order-api itself or Postgres

**Fix:** Repair the dependency that is failing; order-api is usually only the messenger.

## HighLatency

**Meaning:** p95 latency of a service is above 2s.

**Check:** The *p95 latency per service* panel shows which service is slow. order-api is slow if payment or kitchen is slow.
Check the chaos knobs: `LATENCY_MS` on payment-service, `COOK_MIN_MS`/`COOK_MAX_MS` on kitchen-service.
**Fix:** Bring the knob back to normal (`LATENCY_MS=100`, cook 200–800 ms) and `docker compose up -d <service>`.

## PaymentDeclineRateHigh

**Meaning:** Over 20% of payments are declined (normal is about 5%).

**Check:** `docker compose exec payment-service env | grep FAILURE_RATE`
**Fix:** Set `FAILURE_RATE` back to `0.05` and recreate the service.

## NoPizzasServed

**Meaning:** No order has reached `ready` for 5 minutes. Either nothing comes in or everything fails.

**Check:** Is the load generator running (`docker compose ps load-generator`)? Are other alerts firing (TargetDown, HighErrorRate)? Those usually point at the cause.

## HostHighCpu

**Meaning:** The host CPU has been above 90% for 10 minutes.

**Check:** `docker stats --no-stream` to find the container using CPU, or `top` for host processes.

## HostLowMemory

**Meaning:** Less than 10% of memory is available.

**Check:** `docker stats --no-stream`, `free -h`.

## HostDiskAlmostFull

**Meaning:** A filesystem has less than 10% free space. Postgres and Prometheus stop writing when the disk is full.

**Check:**
```bash
df -h
docker system df          # space used by images, containers, volumes, build cache
```
**Fix:** Remove what you don't need, e.g. `docker builder prune` for build cache or `docker image prune` for dangling images. Check what will be deleted first.
