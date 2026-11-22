import asyncio
import os
import random
import time

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel

COOK_MIN_MS = int(os.getenv("COOK_MIN_MS", "200"))
COOK_MAX_MS = int(os.getenv("COOK_MAX_MS", "800"))

REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "path", "status"])
LATENCY = Histogram("http_request_duration_seconds", "HTTP request latency", ["method", "path"])
PIZZAS = Counter("pizzas_cooked_total", "Pizzas cooked", ["pizza"])

app = FastAPI(title="kitchen-service")


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


class CookIn(BaseModel):
    pizza: str


@app.post("/cook")
async def cook(order: CookIn):
    await asyncio.sleep(random.uniform(COOK_MIN_MS, COOK_MAX_MS) / 1000)
    PIZZAS.labels(order.pizza).inc()
    return {"pizza": order.pizza, "status": "ready"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
