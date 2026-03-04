from __future__ import annotations

from typing import Any, Literal

from fastapi import FastAPI, Header, Response
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI(title="JOD_ROBO")

class IntentIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    intent: str = Field(..., min_length=1, max_length=4000)
    context: dict[str, Any] = Field(default_factory=dict)

class IntentOut(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    status: Literal["ok"] = "ok"
    idempotency_key: str
    received_intent: str
    received_context: dict[str, Any]

@app.get("/health", include_in_schema=False)
async def health() -> Response:
    return Response("OK", media_type="text/plain")

@app.get("/healthz", include_in_schema=False)
async def healthz() -> Response:
    return Response("OK", media_type="text/plain")

@app.post("/intent", response_model=IntentOut)
async def post_intent(
    body: IntentIn,
    x_idempotency_key: str = Header(..., alias="x-idempotency-key"),
) -> IntentOut:
    return IntentOut(
        status="ok",
        idempotency_key=x_idempotency_key,
        received_intent=body.intent,
        received_context=body.context,
    )


# =============================
# PATCH JOD_ROBO: /healthz e /intent
# =============================

from typing import Any, Literal
from fastapi import Header, Response
from pydantic import BaseModel, ConfigDict, Field

class JODIntentIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    intent: str = Field(..., min_length=1, max_length=4000)
    context: dict[str, Any] = Field(default_factory=dict)

class JODIntentOut(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    status: Literal["ok"] = "ok"
    idempotency_key: str

@app.get("/healthz", include_in_schema=False)
async def healthz():
    return Response("OK", media_type="text/plain")

@app.post("/intent", response_model=JODIntentOut)
async def intent(
    body: JODIntentIn,
    x_idempotency_key: str = Header(..., alias="x-idempotency-key"),
):
    return JODIntentOut(idempotency_key=x_idempotency_key)
