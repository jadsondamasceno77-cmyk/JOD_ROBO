from fastapi import FastAPI
app = FastAPI()

@app.get("/healthz")
async def healthz():
    return "OK"

@app.get("/")
async def root():
    return {"message": "JOD_ROBO VIVO"}
