from app.main import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


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
