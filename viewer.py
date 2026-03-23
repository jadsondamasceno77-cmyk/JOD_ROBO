import os, json, asyncio, logging, uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field
import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

FACTORY_URL = "http://localhost:37777"
TRUST = os.getenv("JOD_TRUST_MANIFEST", "jod_robo_trust_2026_secure")
APPROVAL_FILE = Path(__file__).resolve().parent / "memory" / "pending_approvals.jsonl"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("JOD_VIEWER")

app = FastAPI(title="JOD_VIEWER", version="1.0")

HEADERS = {
    "x-trust-token": TRUST,
    "x-request-id": "viewer-001",
    "x-idempotency-key": "viewer-idem-001"
}

class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    flow_id: str
    action: str
    params: dict
    decision: str = Field(pattern="^(approve|reject)$")

async def factory_get(path):
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{FACTORY_URL}{path}", headers={**HEADERS, "x-idempotency-key": str(uuid.uuid4())})
        return r.json()

@app.get("/ui", response_class=HTMLResponse)
async def ui():
    agents = await factory_get("/agents")
    audit = await factory_get("/audit")
    pending = []
    if APPROVAL_FILE.exists():
        with open(APPROVAL_FILE) as f:
            for line in f:
                try:
                    e = json.loads(line)
                    if e.get("status") == "pending":
                        pending.append(e)
                except: pass

    agents_html = "".join([f'<tr><td>{a["id"]}</td><td style="color:{"green" if a["status"]=="active" else "orange"}">{a["status"]}</td><td>{a["version"]}</td></tr>' for a in agents])
    audit_html = "".join([f'<tr><td>{e["task_id"][:8]}</td><td>{e["event"]}</td><td>{e["time"][:19]}</td></tr>' for e in audit[:5]])
    pending_html = "".join([f'<tr><td>{p["flow_id"]}</td><td>{p["action"]}</td><td><a href="/approve/{p["flow_id"]}/approve" style="color:green">APROVAR</a> | <a href="/approve/{p["flow_id"]}/reject" style="color:red">REJEITAR</a></td></tr>' for p in pending]) or "<tr><td colspan=3>Nenhuma aprovacao pendente</td></tr>"

    return f"""<!DOCTYPE html><html><head><title>JOD_ROBO</title>
    <meta http-equiv="refresh" content="10">
    <style>body{{font-family:monospace;background:#0a0a0a;color:#00ff41;padding:20px}}
    h1{{color:#00ff41}}h2{{color:#ffaa00}}
    table{{width:100%;border-collapse:collapse;margin-bottom:20px}}
    td,th{{border:1px solid #333;padding:8px;text-align:left}}
    th{{background:#111;color:#ffaa00}}a{{color:#00aaff}}</style></head>
    <body><h1>JOD_ROBO — PAINEL DE CONTROLE</h1>
    <p>Atualizado: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    <h2>AGENTES</h2><table><tr><th>ID</th><th>STATUS</th><th>VERSION</th></tr>{agents_html}</table>
    <h2>AUDITORIA RECENTE</h2><table><tr><th>TASK</th><th>EVENTO</th><th>HORA</th></tr>{audit_html}</table>
    <h2>APROVACOES PENDENTES</h2><table><tr><th>FLOW</th><th>ACAO</th><th>DECISAO</th></tr>{pending_html}</table>
    </body></html>"""

@app.get("/approve/{flow_id}/{decision}", response_class=HTMLResponse)
async def approve(flow_id: str, decision: str):
    if decision not in ("approve", "reject"):
        raise HTTPException(400, "Decisao invalida")
    result_file = Path(__file__).resolve().parent / "memory" / "approval_results.jsonl"
    with open(result_file, "a") as f:
        f.write(json.dumps({"flow_id": flow_id, "decision": decision, "ts": datetime.now(timezone.utc).isoformat()}) + "\n")
    logger.info(f"[VIEWER] {flow_id} -> {decision}")
    return f'<html><body style="background:#0a0a0a;color:#00ff41;font-family:monospace;padding:20px"><h1>{"APROVADO" if decision=="approve" else "REJEITADO"}</h1><p>Flow: {flow_id}</p><a href="/ui">VOLTAR</a></body></html>'

@app.get("/health")
async def health(): return {"status": "alive"}
