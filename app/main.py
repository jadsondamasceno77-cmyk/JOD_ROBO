from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

@app.get("/health")
@app.get("/healthz")
async def health():
    return {"status": "ok"}

@app.post("/intent")
async def intent(data: dict):
    return {"status": "received", "data": data}

@app.get("/")
async def root():
    return {"message": "JOD_ROBO Online"}
