from fastapi import FastAPI
app = FastAPI()

@app.get("/health")
@app.get("/healthz")
async def health():
    return "OK"

@app.get("/")
async def root():
    return {"message": "JOD_ROBO VIVO"}
 
