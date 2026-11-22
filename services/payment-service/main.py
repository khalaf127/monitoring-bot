import asyncio
import os
import random
import time

from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel

# Knobs the incident game will turn later
FAILURE_RATE = float(os.getenv("FAILURE_RATE", "0.05"))
LATENCY_MS = int(os.getenv("LATENCY_MS", "100"))

REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "path", "status"])
LATENCY = Histogram("http_request_duration_seconds", "HTTP request latency", ["method", "path"])
PAYMENTS = Counter("payments_total", "Payments by result", ["result"])

app = FastAPI(title="payment-service")


@app.middleware("http")
async def record_metrics(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    route = request.scope.get("route")
    path = route.path if route else "unmatched"
    if path != "/metrics":
        REQUESTS.labels(request.method, path, response.status_code).inc()
        LATENCY.labels(request.method, path).observe(time.perf_counter() - start)
    return response


class PaymentIn(BaseModel):
    order_id: int


@app.post("/pay")
async def pay(payment: PaymentIn):
    await asyncio.sleep(LATENCY_MS / 1000)
    if random.random() < FAILURE_RATE:
        PAYMENTS.labels("declined").inc()
        raise HTTPException(402, "card declined")
    PAYMENTS.labels("accepted").inc()
    return {"order_id": payment.order_id, "result": "accepted"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
