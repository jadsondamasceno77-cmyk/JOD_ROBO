"""JOD_ROBO API v3.1 — Fachada para jod_brain 10/10."""
import os, asyncio, logging, time, json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","service":"jod_api","msg":"%(message)s"}'
)
logger = logging.getLogger("jod_api")

app = FastAPI(title="JOD_ROBO API", version="3.1.0")
START_TIME = time.time()
JOD_BRAIN_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "jod_brain_main.py")

@app.get("/health")
async def health():
    return {"status": "online", "version": "3.1.0", "uptime": round(time.time() - START_TIME, 2), "engine": "jod_brain_10_10"}

@app.post("/execute")
async def execute(request: Request):
    try:
        body = await request.json()
        task = body.get("task", "")
        if not task:
            return JSONResponse(status_code=400, content={"error": "task vazia"})
        cmd = ["python3", JOD_BRAIN_PATH, task, "--apply", "--api-mode"]
        env = {**os.environ, "GROQ_API_KEY": os.environ.get("GROQ_API_KEY", ""), "JOD_API_MODE": "1"}
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            cwd=os.path.dirname(JOD_BRAIN_PATH), env=env
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=180)
        return {"output": stdout.decode()[:10000], "returncode": proc.returncode, "task": task[:100]}
    except asyncio.TimeoutError:
        return JSONResponse(status_code=504, content={"error": "Timeout: mais de 3 minutos"})
    except Exception as e:
        logger.error(f"Erro em /execute: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)[:500]})

@app.get("/agents")
async def list_agents():
    agents_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "agents")
    if os.path.exists(agents_dir):
        return {"agents": [f for f in os.listdir(agents_dir) if f.endswith(".py") and not f.startswith("_")]}
    return {"agents": []}

@app.get("/scripts")
async def list_scripts():
    scripts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts")
    if os.path.exists(scripts_dir):
        return {"scripts": [f for f in os.listdir(scripts_dir) if f.endswith(".py") and not f.startswith("_")]}
    return {"scripts": []}

@app.get("/memory")
async def get_memory():
    mem_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".jod_memory.json")
    if os.path.exists(mem_path):
        try:
            with open(mem_path) as f:
                mem = json.load(f)
            return {"total_execucoes": len(mem.get("execucoes", [])), "ultimas": mem.get("execucoes", [])[-5:], "aprendizados": mem.get("aprendizados", [])[-3:]}
        except:
            return {"error": "Não foi possível ler memória"}
    return {"memory": "empty"}

@app.get("/")
async def root():
    return {"service": "JOD_ROBO API", "version": "3.1.0", "engine": "jod_brain 10/10",
            "endpoints": {"health": "GET /health", "execute": "POST /execute {\"task\": \"...\"}", "agents": "GET /agents", "scripts": "GET /scripts", "memory": "GET /memory", "docs": "/docs"}}
