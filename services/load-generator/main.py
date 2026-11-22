import asyncio
import os
import random

import httpx

ORDER_API_URL = os.getenv("ORDER_API_URL", "http://order-api:8000")
ORDERS_PER_SECOND = float(os.getenv("ORDERS_PER_SECOND", "2"))
PIZZAS = ["margherita", "pepperoni", "quattro-formaggi", "hawaiian", "veggie"]


async def place_order(client: httpx.AsyncClient):
    pizza = random.choice(PIZZAS)
    try:
        r = await client.post(f"{ORDER_API_URL}/orders", json={"pizza": pizza})
        print(f"{pizza}: {r.status_code}", flush=True)
    except httpx.HTTPError as e:
        print(f"{pizza}: error {e!r}", flush=True)


async def main():
    print(f"Sending ~{ORDERS_PER_SECOND} orders/s to {ORDER_API_URL}", flush=True)
    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            asyncio.create_task(place_order(client))
            # Random gaps so traffic looks like real customers, not a metronome
            await asyncio.sleep(random.expovariate(ORDERS_PER_SECOND))


asyncio.run(main())
