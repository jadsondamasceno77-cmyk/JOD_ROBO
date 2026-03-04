from fastapi import FastAPI, Header
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional

app = FastAPI(title="JOD_ROBO")

@app.get("/health")
async def health():
    return "OK"

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

class IntentIn(BaseModel):
    intent: str = Field(..., min_length=1, max_length=4000)
    context: Dict[str, Any] = {}

@app.post("/intent")
async def intent(body: IntentIn, x_idempotency_key: Optional[str] = Header(default=None, alias="x-idempotency-key")):
    return {
        "status": "received",
        "idempotency_key": x_idempotency_key,
        "intent": body.intent,
        "context": body.context,
    }
