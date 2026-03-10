import os
import time, logging, asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from app.agent import agent, ceo

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
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
            'cd /home/wsl/JOD_ROBO && GROQ_API_KEY="" + os.environ.get("GROQ_API_KEY","") + "" python3 /usr/local/bin/jod_brain.py "' + task + '" --apply',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        stdout, _ = await proc.communicate()
        return {"output": stdout.decode()}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/")
async def ui():
    return "<!DOCTYPE html><html><head><title>JOD EXECUTOR</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0a0a0a;color:#00ff41;font-family:monospace;padding:2rem}
h1{color:#c5a059;margin-bottom:1.5rem}
textarea{background:#111;color:#00ff41;border:1px solid #333;padding:1rem;width:100%;height:100px;font-family:monospace;font-size:15px;resize:vertical;display:block}
button{background:#c5a059;color:#000;border:none;padding:.8rem 2.5rem;cursor:pointer;font-weight:bold;font-size:15px;margin-top:.8rem}
#out{background:#111;border:1px solid #222;padding:1rem;min-height:300px;white-space:pre-wrap;margin-top:1rem;font-size:13px;overflow-y:auto;max-height:60vh}
#st{color:#888;font-size:12px;margin-top:.4rem}
</style></head><body>
<h1>⚡ JOD EXECUTOR</h1>
<textarea id="t" placeholder="Digite a tarefa... ex: cria um agente que busca preços no Google"></textarea>
<button onclick="run()">▶ EXECUTAR</button>
<div id="st"></div>
<div id="out">Aguardando tarefa...</div>
<script>
async function run(){
  const t=document.getElementById('t').value.trim();
  if(!t)return;
  document.getElementById('out').textContent='Executando...';
  document.getElementById('st').textContent='⏳ Processando...';
  try{
    const r=await fetch('/execute',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task:t})});
    const d=await r.json();
    document.getElementById('out').textContent=d.output||d.error;
    document.getElementById('st').textContent='✅ Concluído';
  }catch(e){
    document.getElementById('out').textContent='Erro: '+e;
    document.getElementById('st').textContent='❌ Falhou';
  }
}
document.getElementById('t').addEventListener('keydown',function(e){if(e.ctrlKey&&e.key==='Enter')run()});
</script></body></html>"

@app.get("/teste")
async def teste():
    return {"output": "ok"}
