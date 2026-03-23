import os, json, uuid, asyncio, logging
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, HTTPException, Header, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

FACTORY_URL = "http://localhost:37777"
TRUST = os.getenv("JOD_TRUST_MANIFEST", "jod_robo_trust_2026_secure")
APPROVAL_FILE = Path(__file__).resolve().parent / "memory" / "pending_approvals.jsonl"
RESULTS_FILE = Path(__file__).resolve().parent / "memory" / "approval_results.jsonl"
AUDIT_FILE = Path(__file__).resolve().parent / "memory" / "audit_flow.jsonl"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("JOD_VIEWER")

app = FastAPI(title="JOD_VIEWER", version="2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def gen_headers():
    return {
        "x-trust-token": TRUST,
        "x-request-id": str(uuid.uuid4()),
        "x-idempotency-key": str(uuid.uuid4())
    }

async def factory_get(path):
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{FACTORY_URL}{path}", headers=gen_headers())
        return r.json()

async def factory_post(path, payload):
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{FACTORY_URL}{path}", headers={**gen_headers(), "Content-Type": "application/json"}, json=payload)
        return r.json()

def read_jsonl(path):
    items = []
    if Path(path).exists():
        with open(path) as f:
            for line in f:
                try: items.append(json.loads(line))
                except: pass
    return items

@app.get("/ui", response_class=HTMLResponse)
async def ui():
    try:
        agents = await factory_get("/agents")
        audit = await factory_get("/audit")
    except Exception as e:
        agents, audit = [], []
        logger.error(f"Factory offline: {e}")

    pending = [e for e in read_jsonl(APPROVAL_FILE) if e.get("status") == "pending"]
    audit_full = read_jsonl(AUDIT_FILE)

    agents_html = "".join([
        f'<tr><td>{a["id"]}</td><td style="color:{"#00ff41" if a["status"]=="active" else "#ffaa00"}">{a["status"]}</td><td>{a["version"]}</td><td><a href="/ui/activate/{a["id"]}" style="color:#00aaff">ativar</a></td></tr>'
        for a in agents
    ])

    audit_html = "".join([
        f'<tr><td style="font-size:11px">{e.get("task_id","")[:8]}</td><td>{e.get("event","")}</td><td style="font-size:11px">{e.get("time","")[:19]}</td></tr>'
        for e in audit[:8]
    ])

    audit_deep_html = "".join([
        f'<tr><td style="font-size:10px">{e.get("flow_id","")[:8]}</td><td>{e.get("plan",{}).get("action","")}</td><td style="color:{"#00ff41" if e.get("execution_status")=="succeeded" else "#ff4444"}">{e.get("execution_status","")}</td><td>{str(e.get("validation",{}).get("valid",""))}</td><td style="font-size:10px">{e.get("timestamp","")[:19]}</td></tr>'
        for e in audit_full[-8:]
    ])

    pending_html = "".join([
        f'<tr><td>{p["flow_id"]}</td><td>{p["action"]}</td><td style="font-size:11px">{p.get("ts","")[:19]}</td><td><a href="/ui/approve/{p["flow_id"]}" style="color:#00ff41;font-weight:bold">APROVAR</a> &nbsp; <a href="/ui/reject/{p["flow_id"]}" style="color:#ff4444;font-weight:bold">REJEITAR</a></td></tr>'
        for p in pending
    ]) or "<tr><td colspan=4 style=\'color:#555\'>Nenhuma aprovacao pendente</td></tr>"

    return f"""<!DOCTYPE html><html><head><title>JOD_ROBO v2</title>
    <meta http-equiv="refresh" content="10">
    <style>
    *{{box-sizing:border-box}}
    body{{font-family:monospace;background:#0a0a0a;color:#00ff41;padding:20px;margin:0}}
    h1{{color:#00ff41;font-size:22px;border-bottom:1px solid #1a1a1a;padding-bottom:10px}}
    h2{{color:#ffaa00;font-size:15px;margin-top:24px}}
    table{{width:100%;border-collapse:collapse;margin-bottom:16px;font-size:13px}}
    td,th{{border:1px solid #1a1a1a;padding:7px 10px;text-align:left}}
    th{{background:#111;color:#ffaa00}}
    a{{color:#00aaff;text-decoration:none}}
    a:hover{{text-decoration:underline}}
    .badge-ok{{color:#00ff41}}.badge-warn{{color:#ffaa00}}.badge-err{{color:#ff4444}}
    .status-bar{{display:flex;gap:20px;font-size:12px;color:#555;margin-bottom:16px}}
    .form-row{{display:flex;gap:10px;margin-bottom:16px}}
    input[type=text]{{background:#111;border:1px solid #333;color:#00ff41;padding:6px 10px;font-family:monospace;font-size:13px;flex:1}}
    button{{background:#0a2a0a;border:1px solid #00ff41;color:#00ff41;padding:6px 14px;font-family:monospace;cursor:pointer}}
    button:hover{{background:#1a3a1a}}
    </style></head>
    <body>
    <h1>JOD_ROBO — PAINEL DE CONTROLE v2.0</h1>
    <div class="status-bar">
      <span>Atualizado: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</span>
      <span>Factory: <span class="badge-ok">37777</span></span>
      <span>Viewer: <span class="badge-ok">37778</span></span>
      <span>Trust: <span class="badge-ok">ATIVO</span></span>
      <span>Agentes: <span class="badge-ok">{len(agents)}</span></span>
    </div>

    <h2>CRIAR AGENTE</h2>
    <form action="/ui/create" method="get">
      <div class="form-row">
        <input type="text" name="agent_id" placeholder="ID do agente (ex: agente_coleta)">
        <input type="text" name="name" placeholder="Nome (ex: Agente Coleta)">
        <select name="template" style="background:#111;border:1px solid #333;color:#00ff41;padding:6px;font-family:monospace">
          <option value="executor">executor</option>
          <option value="analyzer">analyzer</option>
          <option value="crawler">crawler</option>
          <option value="scheduler">scheduler</option>
          <option value="support">support</option>
        </select>
        <button type="submit">CRIAR</button>
      </div>
    </form>

    <h2>AGENTES</h2>
    <table><tr><th>ID</th><th>STATUS</th><th>VERSION</th><th>ACAO</th></tr>{agents_html}</table>

    <h2>APROVACOES PENDENTES</h2>
    <table><tr><th>FLOW</th><th>ACAO</th><th>HORA</th><th>DECISAO</th></tr>{pending_html}</table>

    <h2>AUDITORIA FACTORY (tasks)</h2>
    <table><tr><th>TASK</th><th>EVENTO</th><th>HORA</th></tr>{audit_html}</table>

    <h2>AUDITORIA DEEP (flows)</h2>
    <table><tr><th>FLOW</th><th>ACAO</th><th>STATUS</th><th>VALIDO</th><th>HORA</th></tr>{audit_deep_html}</table>

    </body></html>"""

@app.get("/ui/create", response_class=HTMLResponse)
async def ui_create(agent_id: str, name: str, template: str):
    idem = str(uuid.uuid4())
    try:
        r = await factory_post("/agents/create-from-template", {
            "action_type": "create_agent_from_template",
            "parameters": {"template_name": template, "new_agent_id": agent_id, "name": name}
        })
        task_id = r.get("task_id", "?")
        await asyncio.sleep(1)
        result = await factory_get(f"/tasks/{task_id}")
        status = result.get("status", "?")
        return f'<html><body style="background:#0a0a0a;color:#00ff41;font-family:monospace;padding:20px"><h1>AGENTE CRIADO</h1><p>ID: {agent_id}</p><p>Task: {task_id}</p><p>Status: {status}</p><br><a href="/ui">VOLTAR</a></body></html>'
    except Exception as e:
        return f'<html><body style="background:#0a0a0a;color:#ff4444;font-family:monospace;padding:20px"><h1>ERRO</h1><p>{str(e)}</p><a href="/ui">VOLTAR</a></body></html>'

@app.get("/ui/activate/{agent_id}", response_class=HTMLResponse)
async def ui_activate(agent_id: str):
    try:
        r = await factory_post("/agents/validate", {
            "action_type": "validate_agent",
            "parameters": {"agent_id": agent_id}
        })
        await asyncio.sleep(1)
        r2 = await factory_post("/agents/activate", {
            "action_type": "activate_agent",
            "parameters": {"agent_id": agent_id}
        })
        await asyncio.sleep(1)
        result = await factory_get(f"/tasks/{r2.get('task_id','')}")
        return f'<html><body style="background:#0a0a0a;color:#00ff41;font-family:monospace;padding:20px"><h1>AGENTE ATIVADO</h1><p>ID: {agent_id}</p><p>Status: {result.get("status","?")}</p><br><a href="/ui">VOLTAR</a></body></html>'
    except Exception as e:
        return f'<html><body style="background:#0a0a0a;color:#ff4444;font-family:monospace;padding:20px"><h1>ERRO</h1><p>{str(e)}</p><a href="/ui">VOLTAR</a></body></html>'

@app.get("/ui/approve/{flow_id}", response_class=HTMLResponse)
async def ui_approve(flow_id: str):
    with open(RESULTS_FILE, "a") as f:
        f.write(json.dumps({"flow_id": flow_id, "decision": "approve", "ts": datetime.now(timezone.utc).isoformat()}) + "\n")
    logger.info(f"[VIEWER] APROVADO: {flow_id}")
    return f'<html><body style="background:#0a0a0a;color:#00ff41;font-family:monospace;padding:20px"><h1>APROVADO</h1><p>Flow: {flow_id}</p><a href="/ui">VOLTAR</a></body></html>'

@app.get("/ui/reject/{flow_id}", response_class=HTMLResponse)
async def ui_reject(flow_id: str):
    with open(RESULTS_FILE, "a") as f:
        f.write(json.dumps({"flow_id": flow_id, "decision": "reject", "ts": datetime.now(timezone.utc).isoformat()}) + "\n")
    logger.info(f"[VIEWER] REJEITADO: {flow_id}")
    return f'<html><body style="background:#0a0a0a;color:#ff4444;font-family:monospace;padding:20px"><h1>REJEITADO</h1><p>Flow: {flow_id}</p><a href="/ui">VOLTAR</a></body></html>'

@app.get("/health")
async def health():
    try:
        r = await factory_get("/health/live")
        factory_ok = r.get("status") == "alive"
    except:
        factory_ok = False
    return {
        "viewer": "alive",
        "factory": "alive" if factory_ok else "offline",
        "trust": "configured",
        "headers": ["x-trust-token", "x-request-id", "x-idempotency-key"],
        "persistence": "sqlite+jsonl",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
