import time
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from app.agent import agent

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger("jod_robo")

app = FastAPI(title="JOD_ROBO", version="2.0.0")
START_TIME = time.time()

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info("Request: " + request.url.path)
    return await call_next(request)

@app.get("/health")
@app.get("/healthz")
async def health():
    return {"status": "online", "agent": "JOD_ROBO"}

@app.get("/version")
async def version():
    return {"version": "2.0.0", "uptime_seconds": round(time.time() - START_TIME, 2)}

@app.get("/ping")
async def ping():
    return {"ping": "pong", "timestamp": round(time.time(), 2)}

@app.post("/chat")
async def chat(request: Request):
    try:
        body = await request.json()
        reply = await agent.think(body.get("text", ""), body.get("context"))
        return {"reply": reply}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/exec")
async def exec_code(request: Request):
    try:
        body = await request.json()
        result = await agent.execute_python(body.get("code", ""))
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/analyze")
async def analyze(request: Request):
    try:
        body = await request.json()
        result = await agent.analyze_site(body.get("url", ""))
        return {"result": result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/", response_class=HTMLResponse)
async def ui():
    return """<!DOCTYPE html><html><head><title>JOD_ROBO</title>
    <style>body{background:#0d0d0d;color:#fff;font-family:monospace;padding:2rem}
    input,textarea{background:#1a1a1a;color:#fff;border:1px solid #333;padding:.5rem;width:100%;margin:.5rem 0}
    button{background:#c5a059;color:#000;border:none;padding:.5rem 1rem;cursor:pointer}
    #out{background:#1a1a1a;padding:1rem;min-height:200px;white-space:pre-wrap;margin-top:1rem}</style>
    </head><body>
    <h2>⚡ JOD_ROBO v2</h2>
    <input id="q" placeholder="Digite sua mensagem..." onkeydown="if(event.key=='Enter')send()">
    <button onclick="send()">Enviar</button>
    <div id="out">Aguardando...</div>
    <script>
    async function send(){
      const t=document.getElementById('q').value;
      document.getElementById('out').textContent='Pensando...';
      const r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:t})});
      const d=await r.json();
      document.getElementById('out').textContent=d.reply||d.error;
      document.getElementById('q').value='';
    }
    </script></body></html>"""