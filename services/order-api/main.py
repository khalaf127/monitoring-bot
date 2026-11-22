import os
import time

import httpx
import psycopg
from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel

DATABASE_URL = os.environ["DATABASE_URL"]
PAYMENT_URL = os.getenv("PAYMENT_URL", "http://payment-service:8000")
KITCHEN_URL = os.getenv("KITCHEN_URL", "http://kitchen-service:8000")

REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "path", "status"])
LATENCY = Histogram("http_request_duration_seconds", "HTTP request latency", ["method", "path"])
ORDERS = Counter("orders_total", "Orders by final status", ["status"])

app = FastAPI(title="order-api")


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


@app.on_event("startup")
async def init_db():
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                pizza TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT now()
            )
            """
        )


class OrderIn(BaseModel):
    pizza: str


async def set_status(conn, order_id: int, status: str):
    await conn.execute("UPDATE orders SET status = %s WHERE id = %s", (status, order_id))
    ORDERS.labels(status).inc()


@app.post("/orders", status_code=201)
async def create_order(order: OrderIn):
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        cur = await conn.execute(
            "INSERT INTO orders (pizza, status) VALUES (%s, 'pending') RETURNING id", (order.pizza,)
        )
        order_id = (await cur.fetchone())[0]
        await conn.commit()

        async with httpx.AsyncClient(timeout=5) as client:
            try:
                pay = await client.post(f"{PAYMENT_URL}/pay", json={"order_id": order_id})
            except httpx.HTTPError:
                await set_status(conn, order_id, "payment_unreachable")
                raise HTTPException(503, "payment service unreachable")
            if pay.status_code != 200:
                await set_status(conn, order_id, "payment_failed")
                raise HTTPException(402, "payment failed")

            try:
                cook = await client.post(f"{KITCHEN_URL}/cook", json={"pizza": order.pizza})
                cook.raise_for_status()
            except httpx.HTTPError:
                await set_status(conn, order_id, "kitchen_failed")
                raise HTTPException(503, "kitchen service failed")

        await set_status(conn, order_id, "ready")
    return {"id": order_id, "pizza": order.pizza, "status": "ready"}


@app.get("/orders/{order_id}")
async def get_order(order_id: int):
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        cur = await conn.execute("SELECT id, pizza, status FROM orders WHERE id = %s", (order_id,))
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "order not found")
    return {"id": row[0], "pizza": row[1], "status": row[2]}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
