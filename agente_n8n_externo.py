#!/usr/bin/env python3
"""
JOD_ROBO — Agente N8N v4.0 Cognitivo
Cerebro: Groq | Memoria: SQLite | Ferramentas: API REST n8n completa
"""
import asyncio, json, os, sqlite3, uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

load_dotenv(Path(__file__).resolve().parent / ".env")

N8N_URL  = os.getenv("N8N_URL", "http://localhost:5678")
N8N_KEY  = os.getenv("N8N_API_KEY", "")
GROQ_KEY = os.getenv("GROQ_API_KEY", "")
DB_PATH  = os.getenv("DB_PATH", str(Path(__file__).resolve().parent / "jod_robo.db"))
MODEL    = "llama-3.3-70b-versatile"
HEADERS  = {"X-N8N-API-KEY": N8N_KEY, "Content-Type": "application/json"}

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS n8n_sessions (
        session_id TEXT PRIMARY KEY, channel TEXT,
        created_at TEXT, updated_at TEXT, metadata TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS n8n_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT,
        role TEXT, content TEXT, ts TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS n8n_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT,
        mission TEXT, steps TEXT, status TEXT DEFAULT "pending",
        result TEXT, created_at TEXT, updated_at TEXT)""")
    conn.commit()
    conn.close()

def get_or_create_session(sid, channel="api"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute("SELECT session_id FROM n8n_sessions WHERE session_id=?", (sid,))
    if not c.fetchone():
        c.execute("INSERT INTO n8n_sessions VALUES (?,?,?,?,?)", (sid, channel, now, now, "{}"))
        conn.commit()
    conn.close()

def save_message(sid, role, content):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute("INSERT INTO n8n_messages (session_id,role,content,ts) VALUES (?,?,?,?)", (sid, role, content, now))
    c.execute("UPDATE n8n_sessions SET updated_at=? WHERE session_id=?", (now, sid))
    conn.commit()
    conn.close()

def get_history(sid, limit=8):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT role,content FROM n8n_messages WHERE session_id=? ORDER BY id DESC LIMIT ?", (sid, limit))
    rows = c.fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

def save_plan(sid, mission, steps):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute("INSERT INTO n8n_plans (session_id,mission,steps,status,created_at,updated_at) VALUES (?,?,?,?,?,?)",
              (sid, mission, json.dumps(steps), "running", now, now))
    pid = c.lastrowid
    conn.commit()
    conn.close()
    return pid

def update_plan(pid, status, result):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute("UPDATE n8n_plans SET status=?,result=?,updated_at=? WHERE id=?", (status, result, now, pid))
    conn.commit()
    conn.close()

async def n8n_get(path):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{N8N_URL}/api/v1{path}", headers=HEADERS)
        r.raise_for_status()
        return r.json()

async def n8n_post(path, payload):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(f"{N8N_URL}/api/v1{path}", headers=HEADERS, json=payload)
        if not r.is_success:
            raise Exception(f"n8n {r.status_code}: {r.text[:200]}")
        return r.json()

async def n8n_patch(path, payload):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.patch(f"{N8N_URL}/api/v1{path}", headers=HEADERS, json=payload)
        r.raise_for_status()
        return r.json()

async def n8n_put(path, payload):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.put(f"{N8N_URL}/api/v1{path}", headers=HEADERS, json=payload)
        r.raise_for_status()
        return r.json()

async def n8n_delete(path):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.delete(f"{N8N_URL}/api/v1{path}", headers=HEADERS)
        r.raise_for_status()
        return r.json()

async def tool_list_workflows():
    r = await n8n_get("/workflows")
    return [{"id": w["id"], "name": w["name"], "active": w["active"]} for w in r.get("data", [])]

async def tool_get_workflow(wf_id):
    return await n8n_get(f"/workflows/{wf_id}")

async def tool_list_nodes(wf_id):
    wf = await tool_get_workflow(wf_id)
    return [{"name": n["name"], "type": n["type"].split(".")[-1], "id": n.get("id","")}
            for n in wf.get("nodes", [])]

async def tool_get_connections(wf_id):
    wf = await tool_get_workflow(wf_id)
    return wf.get("connections", {})

async def tool_connect_nodes(wf_id, source, target, src_out=0, tgt_in=0):
    wf = await tool_get_workflow(wf_id)
    nodes = wf["nodes"]
    conns = wf.get("connections", {})
    names = [n["name"] for n in nodes]
    if source not in names:
        raise Exception(f"No '{source}' nao encontrado. Disponiveis: {names}")
    if target not in names:
        raise Exception(f"No '{target}' nao encontrado. Disponiveis: {names}")
    if source not in conns:
        conns[source] = {"main": [[]]}
    while len(conns[source]["main"]) <= src_out:
        conns[source]["main"].append([])
    existing = conns[source]["main"][src_out]
    if any(c["node"] == target and c["index"] == tgt_in for c in existing):
        return {"status": "already_connected", "source": source, "target": target}
    conns[source]["main"][src_out].append({"node": target, "type": "main", "index": tgt_in})
    await n8n_put(f"/workflows/{wf_id}", {
        "name": wf["name"], "nodes": nodes,
        "connections": conns, "settings": wf.get("settings", {})})
    return {"status": "connected", "source": source, "target": target}

async def tool_activate(wf_id):
    async with __import__("httpx").AsyncClient(timeout=15) as c:
        r = await c.post(f"{N8N_URL}/api/v1/workflows/{wf_id}/activate", headers=HEADERS)
        if not r.is_success: raise Exception(f"activate {r.status_code}: {r.text[:200]}")
        return r.json()

async def tool_deactivate(wf_id):
    return await n8n_patch(f"/workflows/{wf_id}", {"active": False})

async def tool_execute(wf_id):
    return await n8n_post(f"/workflows/{wf_id}/run", {})

async def tool_list_executions(wf_id=None, limit=10):
    path = f"/executions?limit={limit}"
    if wf_id:
        path += f"&workflowId={wf_id}"
    return await n8n_get(path)

async def tool_disconnect_nodes(wf_id, source, target):
    wf = await tool_get_workflow(wf_id)
    conns = wf.get("connections", {})
    if source in conns:
        conns[source]["main"] = [
            [c for c in out if c["node"] != target]
            for out in conns[source].get("main", [[]])]
    await n8n_put(f"/workflows/{wf_id}", {
        "name": wf["name"], "nodes": wf["nodes"],
        "connections": conns, "settings": wf.get("settings", {})})
    return {"status": "disconnected", "source": source, "target": target}

async def tool_delete(wf_id):
    return await n8n_delete(f"/workflows/{wf_id}")

async def execute_tool(tool, params):
    try:
        if tool == "list_workflows":
            return {"status": "ok", "result": await tool_list_workflows()}
        elif tool == "list_nodes":
            return {"status": "ok", "result": await tool_list_nodes(params["wf_id"])}
        elif tool == "get_connections":
            return {"status": "ok", "result": await tool_get_connections(params["wf_id"])}
        elif tool == "connect_nodes":
            return {"status": "ok", "result": await tool_connect_nodes(
                params["wf_id"], params["source"], params["target"],
                params.get("source_output",0), params.get("target_input",0))}
        elif tool == "disconnect_nodes":
            return {"status": "ok", "result": await tool_disconnect_nodes(
                params["wf_id"], params["source"], params["target"])}
        elif tool == "activate_workflow":
            return {"status": "ok", "result": await tool_activate(params["wf_id"])}
        elif tool == "deactivate_workflow":
            return {"status": "ok", "result": await tool_deactivate(params["wf_id"])}
        elif tool == "execute_workflow":
            return {"status": "ok", "result": await tool_execute(params["wf_id"])}
        elif tool == "list_executions":
            return {"status": "ok", "result": await tool_list_executions(
                params.get("wf_id"), params.get("limit",10))}
        elif tool == "delete_workflow":
            return {"status": "ok", "result": await tool_delete(params["wf_id"])}
        else:
            return {"status": "error", "result": f"Ferramenta desconhecida: {tool}"}
    except Exception as e:
        return {"status": "error", "result": str(e)}

SYSTEM_PLANNER = """Voce eh o Agente N8N Cognitivo do JOD_ROBO. Age como especialista humano em n8n.
Ferramentas: list_workflows, list_nodes(wf_id), get_connections(wf_id), connect_nodes(wf_id,source,target),
disconnect_nodes(wf_id,source,target), activate_workflow(wf_id), deactivate_workflow(wf_id),
execute_workflow(wf_id), list_executions(wf_id,limit), delete_workflow(wf_id).
Retorne APENAS JSON valido sem markdown:
{"mission":"...","steps":[{"step":1,"description":"...","tool":"...","params":{...},"depends_on":[]}],"expected_outcome":"..."}"""

SYSTEM_EVAL = """Voce avalia o resultado de uma ferramenta n8n e decide o proximo passo.
Retorne APENAS JSON valido sem markdown:
{"evaluation":"ok|error","extracted_info":{},"next_action":"continue|abort","summary":"1 linha"}"""

async def call_groq(messages, system, temperature=0.1):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
            json={"model": MODEL, "messages": [{"role":"system","content":system}]+messages,
                  "temperature": temperature, "max_tokens": 1500})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()

def parse_json(text):
    try:
        return json.loads(text)
    except Exception:
        import re
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
    return {"error": "parse_failed", "raw": text[:300]}

async def cognitive_execute(mission, session_id, channel="api"):
    get_or_create_session(session_id, channel)
    save_message(session_id, "user", mission)
    history = get_history(session_id, limit=6)
    try:
        workflows = await tool_list_workflows()
        ctx = f"Workflows: {json.dumps(workflows, ensure_ascii=False)}"
    except Exception as e:
        ctx = f"Erro ao buscar workflows: {e}"
    plan_raw = await call_groq(
        history + [{"role":"user","content":f"Missao: {mission}\n\n{ctx}"}],
        SYSTEM_PLANNER)
    plan = parse_json(plan_raw)
    if "error" in plan:
        return {"status":"error","message":"Falha no planejamento","raw":plan_raw}
    steps = plan.get("steps", [])
    if not steps:
        return {"status":"error","message":"Plano sem passos","plan":plan}
    plan_id = save_plan(session_id, mission, steps)
    results = []
    accumulated = {}
    for step in steps:
        num   = step.get("step","?")
        tool  = step.get("tool","")
        params = step.get("params",{})
        desc  = step.get("description","")
        params_str = json.dumps(params)
        for k,v in accumulated.items():
            params_str = params_str.replace(f"{{{k}}}", str(v))
        try:
            params = json.loads(params_str)
        except Exception:
            pass
        tool_result = await execute_tool(tool, params)
        eval_raw = await call_groq(
            [{"role":"user","content":json.dumps({
                "step":num,"tool":tool,"params":params,
                "result":tool_result,"accumulated":accumulated
            },ensure_ascii=False)}], SYSTEM_EVAL)
        evaluation = parse_json(eval_raw)
        accumulated.update(evaluation.get("extracted_info",{}))
        results.append({"step":num,"description":desc,"tool":tool,
                        "result":tool_result,"evaluation":evaluation.get("evaluation","?"),
                        "summary":evaluation.get("summary","")})
        if evaluation.get("next_action") == "abort":
            update_plan(plan_id, "aborted", json.dumps(results))
            msg = f"Abortado no passo {num}: {evaluation.get('summary','')}"
            save_message(session_id, "assistant", msg)
            return {"status":"aborted","steps_executed":len(results),"results":results,"summary":msg}
        await asyncio.sleep(0.3)
    update_plan(plan_id, "completed", json.dumps(results))
    lines = [f"Missao concluida: {plan.get('mission', mission)}"]
    for r in results:
        icon = "OK" if r["result"]["status"]=="ok" else "ERRO"
        lines.append(f"  [{icon}] Passo {r['step']}: {r['summary'] or r['description']}")
    summary = "\n".join(lines)
    save_message(session_id, "assistant", summary)
    return {"status":"completed","plan":plan,"steps_executed":len(results),
            "results":results,"accumulated":accumulated,"summary":summary}

app = FastAPI(title="JOD N8N Agent v4.0 Cognitivo")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def startup():
    init_db()

@app.get("/health")
async def health():
    try:
        wfs = await tool_list_workflows()
        n8n_ok = f"ok ({len(wfs)} workflows)"
    except Exception as e:
        n8n_ok = f"error: {e}"
    return {"status":"ok","agent":"n8n-cognitivo-v4","n8n":n8n_ok,"model":MODEL}

@app.post("/execute")
async def execute(request: Request):
    body = await request.json()
    task = body.get("task","")
    sid  = body.get("session_id") or str(uuid.uuid4())
    chan = body.get("channel","api")
    if not task:
        return JSONResponse({"status":"error","message":"Campo task obrigatorio"}, status_code=400)
    result = await cognitive_execute(task, sid, chan)
    result["session_id"] = sid
    return JSONResponse(result)

@app.post("/connect")
async def connect_direct(request: Request):
    body = await request.json()
    try:
        r = await tool_connect_nodes(
            body["wf_id"], body["source"], body["target"],
            body.get("source_output",0), body.get("target_input",0))
        return JSONResponse({"status":"ok","result":r})
    except Exception as e:
        return JSONResponse({"status":"error","message":str(e)}, status_code=400)

@app.get("/workflows")
async def list_wf():
    return JSONResponse({"status":"ok","workflows": await tool_list_workflows()})

@app.get("/workflows/{wf_id}/nodes")
async def nodes(wf_id: str):
    return JSONResponse({"status":"ok","nodes": await tool_list_nodes(wf_id)})

@app.get("/workflows/{wf_id}/connections")
async def conns(wf_id: str):
    return JSONResponse({"status":"ok","connections": await tool_get_connections(wf_id)})

@app.post("/workflows/{wf_id}/activate")
async def activate(wf_id: str):
    return JSONResponse({"status":"ok","result": await tool_activate(wf_id)})

@app.post("/workflows/{wf_id}/execute")
async def run_wf(wf_id: str):
    return JSONResponse({"status":"ok","result": await tool_execute(wf_id)})

@app.get("/sessions/{session_id}/history")
async def history(session_id: str):
    return JSONResponse({"status":"ok","history": get_history(session_id, 20)})

if __name__ == "__main__":
    init_db()
    uvicorn.run("agente_n8n_externo:app", host="0.0.0.0", port=37780, reload=False)
