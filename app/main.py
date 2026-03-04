from fastapi import FastAPI
app = FastAPI()

@app.get("/")
@app.get("/health")
@app.get("/healthz")
async def health():
    return "OK"

@app.post("/intent")
@app.get("/intent")
async def intent(data: dict = None):
    return {"status": "received", "data": data}
