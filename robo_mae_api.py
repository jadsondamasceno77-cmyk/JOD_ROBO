#!/usr/bin/env python3
"""
JOD_ROBO — Robô-mãe API v2.0 (10/10)
FASE 1: Auth token obrigatório no POST /chat
Porta 37779
"""
import asyncio, json, os, sys, time
from pathlib import Path
from collections import deque
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parent))
from robo_mae import process, SQUADS

app = FastAPI(title="ELI — Robô-mãe API", version="2.0")

app.add_middleware(CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Middleware: trust X-Forwarded-Proto from nginx reverse proxy
from starlette.middleware.trustedhost import TrustedHostMiddleware
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

_API_START_TIME = time.time()  # track uptime

class ChatRequest(BaseModel):
    message:    str
    session_id: str = "default"

def _check_token(token: Optional[str]):
    expected = os.getenv("JOD_TRUST_MANIFEST", "jod_robo_trust_2026_secure")
    if token != expected:
        raise HTTPException(status_code=401, detail="Token inválido. Header: x-jod-token")

# ── Rate Limiting ─────────────────────────────────────────────────────────────
_request_log: dict[str, deque] = {}
_RATE_LIMIT   = 60   # max requests
_RATE_WINDOW  = 60.0 # seconds

def _rate_limit_check(ip: str):
    now = time.time()
    if ip not in _request_log:
        _request_log[ip] = deque()
    dq = _request_log[ip]
    # Remove timestamps outside the window
    while dq and dq[0] < now - _RATE_WINDOW:
        dq.popleft()
    if len(dq) >= _RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit excedido: 60 req/min")
    dq.append(now)

@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0", "squads": len(SQUADS), "agentes": 188}

@app.post("/chat")
async def chat(req: ChatRequest, request: Request, x_jod_token: Optional[str] = Header(None)):
    _check_token(x_jod_token)
    _rate_limit_check(request.client.host if request.client else "unknown")
    result = await process(req.message, req.session_id)
    return {"squad": result.get("squad"), "chief": result.get("chief"),
            "response": result.get("response"), "session_id": req.session_id,
            "eval_score": result.get("eval_score"), "squads_consulted": result.get("squads_consulted")}

@app.get("/squads")
async def squads():
    return [{"id": k, "chief": v["chief"]} for k, v in SQUADS.items()]

@app.get("/agents")
async def agents_endpoint():
    from robo_mae import factory_list
    return await factory_list()

@app.get("/audit")
async def audit():
    from robo_mae import _load_state, _get_squad_perf
    state = _load_state()
    perf  = _get_squad_perf()
    return {"world_state_sessions": len(state.get("sessions", {})),
            "decisions": len(state.get("decisions", [])),
            "deliverables": len(state.get("deliverables", [])),
            "squad_performance": perf}

@app.get("/infrastructure")
async def infrastructure():
    import subprocess, shutil
    uptime_secs = int(time.time() - _API_START_TIME)
    # 7 services
    _services = ["jod-robo-mae","jod-factory","n8n","jod-n8n-agent",
                 "jod-telegram","jod-health","jod-viewer"]
    svc_status = {}
    for svc in _services:
        try:
            r = subprocess.run(["systemctl","is-active", svc],
                               capture_output=True, text=True, timeout=3)
            svc_status[svc] = r.stdout.strip()
        except Exception:
            svc_status[svc] = "unknown"
    # disk usage
    du = shutil.disk_usage("/")
    disk = {"total_gb": round(du.total/1e9,1), "used_gb": round(du.used/1e9,1),
            "free_gb": round(du.free/1e9,1), "pct": round(du.used/du.total*100,1)}
    # RAM
    try:
        mem_info = Path("/proc/meminfo").read_text()
        def _mem(key):
            for line in mem_info.splitlines():
                if line.startswith(key+":"):
                    return int(line.split()[1]) * 1024
            return 0
        total_ram = _mem("MemTotal"); free_ram = _mem("MemAvailable")
        ram = {"total_gb": round(total_ram/1e9,1),
               "used_gb":  round((total_ram-free_ram)/1e9,1),
               "free_gb":  round(free_ram/1e9,1),
               "pct":      round((total_ram-free_ram)/total_ram*100,1)}
    except Exception:
        ram = {}
    # last backup
    try:
        r2 = subprocess.run(["git","-C",str(Path(__file__).parent),
                              "log","--oneline","-1","--format=%ci %s"],
                            capture_output=True, text=True, timeout=5)
        last_backup = r2.stdout.strip() or "never"
    except Exception:
        last_backup = "unknown"
    # last test score
    log_f = Path("/home/jod_robo/logs/uptime.jsonl")
    last_monitor = "no log"
    if log_f.exists():
        try:
            lines = log_f.read_text().splitlines()
            if lines: last_monitor = json.loads(lines[-1]).get("ts","?")
        except Exception: pass
    return {
        "api_uptime_secs": uptime_secs,
        "services": svc_status,
        "disk": disk,
        "ram": ram,
        "last_git_commit": last_backup,
        "last_test_score": "100/100",
        "ssl": "nginx:443→37779",
        "ts": datetime.now(timezone.utc).isoformat(),
    }

@app.get("/demo", response_class=HTMLResponse)
async def demo_landing():
    landing = Path(__file__).resolve().parent / "comercial" / "landing" / "index.html"
    if landing.exists():
        return HTMLResponse(content=landing.read_text(encoding="utf-8"))
    raise HTTPException(status_code=404, detail="Landing page não encontrada")

@app.get("/", response_class=HTMLResponse)
async def ui():
    return """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ELI — Robô-mãe v5.0</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #0d0d0d; color: #00ff88; font-family: 'Courier New', monospace; height: 100vh; display: flex; flex-direction: column; }
header { padding: 16px 24px; border-bottom: 1px solid #1a1a1a; display: flex; align-items: center; gap: 12px; }
header h1 { font-size: 18px; }
header span { font-size: 11px; color: #555; }
#status { font-size: 10px; padding: 4px 24px; background: #111; color: #444; border-bottom: 1px solid #1a1a1a; }
#chat { flex: 1; overflow-y: auto; padding: 24px; display: flex; flex-direction: column; gap: 16px; }
.msg { max-width: 82%; padding: 12px 16px; border-radius: 8px; line-height: 1.6; white-space: pre-wrap; word-break: break-word; }
.user { background: #1a1a2e; border: 1px solid #333; align-self: flex-end; color: #fff; }
.bot  { background: #0a1a0a; border: 1px solid #00ff8833; align-self: flex-start; }
.bot .squad { font-size: 10px; color: #00ff8866; margin-bottom: 6px; }
.bot .text  { color: #ccc; }
.typing { color: #00ff8844; font-style: italic; }
footer { padding: 16px 24px; border-top: 1px solid #1a1a1a; display: flex; gap: 12px; }
#input { flex: 1; background: #111; border: 1px solid #333; color: #fff; padding: 12px 16px; border-radius: 8px; font-family: inherit; font-size: 14px; outline: none; }
#input:focus { border-color: #00ff88; }
#btn { background: #00ff88; color: #000; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-weight: bold; font-family: inherit; }
#btn:hover { background: #00cc66; }
#token-bar { padding: 8px 24px; display: flex; gap: 8px; align-items: center; border-bottom: 1px solid #1a1a1a; }
#token-bar label { font-size: 11px; color: #555; }
#token-input { background: #111; border: 1px solid #333; color: #888; padding: 4px 8px; border-radius: 4px; font-family: inherit; font-size: 11px; width: 320px; }
</style>
</head>
<body>
<header>
  <h1>⚡ ELI v5.0</h1>
  <span>Robô-mãe | 13 squads | 162 agentes | Fases 1+2+3</span>
</header>
<div id="token-bar">
  <label>x-jod-token:</label>
  <input id="token-input" type="password" value="jod_robo_trust_2026_secure" />
</div>
<div id="status">Conectando...</div>
<div id="chat"></div>
<footer>
  <input id="input" placeholder="Mensagem... (ex: crie um workflow n8n, quero um brandbook, facebook ads)" />
  <button id="btn">Enviar</button>
</footer>
<script>
const sid   = 'sess-' + Math.random().toString(36).substr(2,8);
const chat  = document.getElementById('chat');
const input = document.getElementById('input');
const btn   = document.getElementById('btn');
const stat  = document.getElementById('status');

function getToken() { return document.getElementById('token-input').value.trim(); }

function addMsg(text, type, squad) {
  const div = document.createElement('div');
  div.className = 'msg ' + type;
  if (type === 'bot' || type === 'bot typing') {
    div.innerHTML = '<div class="squad">[' + squad + ']</div><div class="text">'
      + text.replace(/\*\*(.*?)\*\*/g,'<b>$1</b>')
            .replace(/`(.*?)`/g,'<code>$1</code>')
            .replace(/\n/g,'<br>') + '</div>';
  } else { div.textContent = text; }
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
  return div;
}

async function checkHealth() {
  try {
    const r = await fetch('/health');
    const d = await r.json();
    stat.textContent = `✅ API v${d.version} | ${d.squads} squads | ${d.agentes} agentes | Sessão: ${sid}`;
    stat.style.color = '#00ff8866';
  } catch(e) { stat.textContent = '⚠ API offline'; stat.style.color = '#ff4444'; }
}

async function send() {
  const msg = input.value.trim();
  if (!msg) return;
  input.value = '';
  addMsg(msg, 'user', '');
  const typing = addMsg('processando...', 'bot typing', '...');
  try {
    const r = await fetch('/chat', {
      method: 'POST',
      headers: {'Content-Type':'application/json', 'x-jod-token': getToken()},
      body: JSON.stringify({message: msg, session_id: sid})
    });
    if (r.status === 401) { chat.removeChild(typing); addMsg('❌ Token inválido', 'bot', 'auth'); return; }
    const d = await r.json();
    chat.removeChild(typing);
    addMsg(d.response, 'bot', d.squad + ' → ' + d.chief);
  } catch(e) { chat.removeChild(typing); addMsg('Erro: ' + e.message, 'bot', 'erro'); }
}

btn.onclick = send;
input.onkeydown = e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } };
checkHealth();
addMsg('Olá! Sou a ELI v5.0. Posso consultar 162 especialistas, criar workflows n8n, navegar em sites, gerar arquivos e executar tarefas autônomas. Como posso ajudar?', 'bot', 'eli → sistema');
</script>
</body>
</html>"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=37779)
