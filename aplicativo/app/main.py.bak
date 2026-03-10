from fastapi import FastAPI
app = FastAPI()

@app.get("/health")
@app.get("/healthz")
async def health():
    return "OK"

@app.post("/intent")
async def intent(data: dict):
    return {"status": "received", "data": data}

@app.get("/")
async def root():
    return {"message": "JOD_ROBO ONLINE"}
