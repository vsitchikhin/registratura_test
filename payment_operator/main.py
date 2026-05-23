import asyncio
import random
import uuid

import httpx
from fastapi import BackgroundTasks, FastAPI
from pydantic import BaseModel

app = FastAPI()


class PaymentRequest(BaseModel):
    payment_id: str
    amount_minor: str
    currency: str
    idempotency_key: str
    webhook_url: str


async def process_payment(req: PaymentRequest):
    await asyncio.sleep(random.uniform(1, 3))

    event_id = str(uuid.uuid4())
    status = "succeeded" if random.random() < 0.8 else "failed"
    payload = {
        "event_id": event_id,
        "payment_id": req.payment_id,
        "operator_payment_id": str(uuid.uuid4()),
        "status": status,
    }

    async with httpx.AsyncClient() as client:
        await client.post(req.webhook_url, json=payload, timeout=10)

        if random.random() < 0.2:
            await asyncio.sleep(0.5)
            await client.post(req.webhook_url, json=payload, timeout=10)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/payments", status_code=202)
async def create_payment(req: PaymentRequest, bg: BackgroundTasks):
    bg.add_task(process_payment, req)
    return {"status": "accepted", "operator_payment_id": str(uuid.uuid4())}
