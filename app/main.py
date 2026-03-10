import os, time, logging, asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from app.agent import agent, ceo

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("jod_robo")
app = FastAPI(title="JOD_ROBO", version="2.0.0")
START_TIME = time.time()

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info("Request: " + request.url.path)
    return await call_next(request)

@app.get("/health")
async def health():
    return {"status": "online", "agent": "JOD_ROBO"}

@app.get("/version")
async def version():
    return {"version": "2.0.0", "uptime_seconds": round(time.time() - START_TIME, 2)}

@app.get("/ping")
async def ping():
    return {"ping": "pong", "timestamp": time.time()}

@app.post("/execute")
async def execute(request: Request):
    try:
        body = await request.json()
        task = body.get("task", "")
        proc = await asyncio.create_subprocess_shell(
            "cd /home/wsl/JOD_ROBO && python3 /usr/local/bin/jod_brain.py \"" + task + "\" --apply",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env={**os.environ, "GROQ_API_KEY": os.environ.get("GROQ_API_KEY","")}
        )
        stdout, _ = await proc.communicate()
        return {"output": stdout.decode()}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/", response_class=HTMLResponse)
async def ui():
    html = open("/home/wsl/JOD_ROBO/app/ui.html").read()
    return html
