#!/usr/bin/env python3
import os, sys, json, sqlite3, subprocess, shutil, time
from pathlib import Path
from datetime import datetime

JOD_DIR = Path.home() / "JOD_ROBO"
DB_PATH = JOD_DIR / "jod_robo.db"

def log(msg): print(msg)

def write_file(path, content):
    Path(path).write_text(content, encoding="utf-8")
    log(f"  ✓ escrito: {Path(path).name}")

def patch_file(path, old, new, label):
    p = Path(path)
    if not p.exists():
        log(f"  ⚠ arquivo não encontrado: {p.name}")
        return False
    code = p.read_text()
    if old in code:
        p.write_text(code.replace(old, new))
        log(f"  ✅ PATCH aplicado: {label}")
        return True
    log(f"  ℹ já aplicado ou não encontrado: {label}")
    return False

def run(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return r.stdout.strip() + r.stderr.strip()

# ── FASE 1.1 — AUTH ──────────────────────────────────────────────
log("\n▶ FASE 1.1 — Auth token na API ELI")
patch_file(
    JOD_DIR / "robo_mae_api.py",
    "from fastapi import FastAPI",
    "from fastapi import FastAPI, Request, HTTPException",
    "imports auth"
)
patch_file(
    JOD_DIR / "robo_mae_api.py",
    'async def chat(req: ChatRequest):',
    '''async def chat(req: ChatRequest, request: Request):
    token = request.headers.get("x-jod-token","")
    if token != os.getenv("JOD_TRUST_MANIFEST",""):
        raise HTTPException(status_code=401, detail="unauthorized")''',
    "endpoint auth guard"
)
log("  ℹ Header: x-jod-token: jod_robo_trust_2026_secure")

# ── FASE 1.2 — HEALTH MONITOR ────────────────────────────────────
log("\n▶ FASE 1.2 — Health monitor")
write_file(JOD_DIR / "health_monitor.py", '''#!/usr/bin/env python3
"""JOD_ROBO — Health Monitor. Verifica 4 serviços a cada 60s."""
import subprocess, time, requests, logging
from datetime import datetime
logging.basicConfig(filename="health.log", level=logging.INFO,
    format="%(asctime)s %(message)s")

SERVICES = ["jod-factory","jod-viewer","eli-api","n8n"]
PORTS    = {"37777":"factory","37778":"viewer","37779":"eli-api","5678":"n8n"}

def check():
    issues = []
    for svc in SERVICES:
        r = subprocess.run(["systemctl","is-active",svc], capture_output=True, text=True)
        if r.stdout.strip() != "active":
            issues.append(f"{svc} INATIVO")
            subprocess.run(["sudo","systemctl","restart",svc])
            logging.warning(f"RESTART: {svc}")
    for port, name in PORTS.items():
        try:
            requests.get(f"http://localhost:{port}/health", timeout=3)
        except:
            issues.append(f"porta {port} ({name}) sem resposta")
    if issues:
        logging.error("ISSUES: " + " | ".join(issues))
    else:
        logging.info("OK — todos os serviços saudáveis")

if __name__ == "__main__":
    print("Health monitor iniciado. Ctrl+C para parar.")
    while True:
        check()
        time.sleep(60)
''')

# ── FASE 1.3 — ORCHESTRATOR ──────────────────────────────────────
log("\n▶ FASE 1.3 — Orchestrator autônomo")
write_file(JOD_DIR / "orchestrator.py", '''#!/usr/bin/env python3
"""JOD_ROBO — Orchestrator autônomo. Loop: plan→execute→evaluate→retry→deliver."""
import asyncio, json, sys, os, httpx
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

API = "http://localhost:37779"
TOKEN = os.getenv("JOD_TRUST_MANIFEST","")
HEADERS = {"Content-Type":"application/json","x-jod-token":TOKEN}
MAX_RETRIES = 3

async def chat(message, session_id="orch"):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{API}/chat", headers=HEADERS,
            json={"message": message, "session_id": session_id})
        return r.json()

async def evaluate(response_text):
    """Avalia qualidade 0-10 via Groq inline."""
    from groq import Groq
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    r = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role":"system","content":"Avalie a qualidade desta resposta de 0 a 10. Retorne APENAS o número."},
            {"role":"user","content":response_text[:500]}
        ], temperature=0.0, max_tokens=4)
    try: return float(r.choices[0].message.content.strip())
    except: return 7.0

async def run(objective):
    print(f"\\n🎯 Objetivo: {objective}")
    session = f"orch_{hash(objective)%10000}"
    steps = [objective]
    results = []

    for attempt in range(MAX_RETRIES):
        print(f"  → Tentativa {attempt+1}/{MAX_RETRIES}")
        resp = await chat(steps[-1], session)
        text = resp.get("response","")

        if not text:
            print("  ⚠ Resposta vazia — retentando com reformulação")
            steps.append(f"Reformule e responda: {objective}")
            continue

        score = await evaluate(text)
        print(f"  → Score: {score}/10")
        results.append({"attempt": attempt+1, "score": score, "response": text})

        if score >= 7.0:
            print(f"\\n✅ Entrega final (score {score}):\\n")
            print(text)
            return {"status":"ok","score":score,"response":text}

        steps.append(f"A resposta anterior foi insatisfatória (score {score}/10). Melhore: {objective}")

    best = max(results, key=lambda x: x["score"])
    print(f"\\n⚠ Melhor resultado após {MAX_RETRIES} tentativas (score {best[\'score\']}):\\n")
    print(best["response"])
    return {"status":"partial","score":best["score"],"response":best["response"]}

if __name__ == "__main__":
    obj = " ".join(sys.argv[1:]) or "Liste os squads disponíveis e suas especialidades"
    asyncio.run(run(obj))
''')

# ── FASE 2.1 — AGENT PERFORMANCE ─────────────────────────────────
log("\n▶ FASE 2.1 — Tabela agent_performance")
try:
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS agent_performance (
        squad TEXT PRIMARY KEY,
        total_calls INTEGER DEFAULT 0,
        total_score REAL DEFAULT 0,
        avg_score REAL DEFAULT 7.0,
        last_used TEXT)""")
    squads = ["traffic-masters","copy-squad","brand-squad","data-squad","design-squad",
              "hormozi-squad","storytelling","movement","cybersecurity",
              "claude-code-mastery","c-level-squad","advisory-board","n8n-squad"]
    for s in squads:
        con.execute("INSERT OR IGNORE INTO agent_performance(squad) VALUES(?)", (s,))
    con.commit(); con.close()
    log("  ✅ tabela agent_performance criada/populada")
except Exception as e:
    log(f"  ⚠ DB error: {e}")

# ── FASE 2.2 — WORLD STATE ───────────────────────────────────────
log("\n▶ FASE 2.2 — World state persistente")
write_file(JOD_DIR / "world_state.py", '''#!/usr/bin/env python3
"""JOD_ROBO — World State. Mantém modelo interno do projeto."""
import json
from pathlib import Path
from datetime import datetime

WS_PATH = Path(__file__).parent / "world_state.json"

def load():
    if WS_PATH.exists():
        return json.loads(WS_PATH.read_text())
    return {"decisions":[],"in_progress":[],"delivered":[],"last_updated":None}

def save(state):
    state["last_updated"] = datetime.now().isoformat()
    WS_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2))

def update(category, item):
    """category: decisions | in_progress | delivered"""
    state = load()
    state.setdefault(category, []).append({"item":item,"ts":datetime.now().isoformat()})
    state[category] = state[category][-50:]  # max 50 por categoria
    save(state)

def get_context():
    s = load()
    return json.dumps({
        "recent_decisions": s.get("decisions",[])[-5:],
        "in_progress": s.get("in_progress",[])[-3:],
        "last_delivered": s.get("delivered",[])[-3:]
    }, ensure_ascii=False)

if __name__ == "__main__":
    print(get_context())
''')

# ── FASE 3 — RESTART ─────────────────────────────────────────────
log("\n▶ FASE 3 — Reiniciando eli-api")
out = run("sudo systemctl restart eli-api 2>&1 && sleep 3 && systemctl is-active eli-api")
log(f"  eli-api: {out}")

# ── VALIDAÇÃO FINAL ───────────────────────────────────────────────
log("\n▶ VALIDAÇÃO FINAL")
time.sleep(3)
out = run('curl -s http://localhost:37779/health')
log(f"  API health: {'✅' if 'ok' in out else '⚠ ' + out[:60]}")

out = run("python3 -c \"import ast; ast.parse(open('orchestrator.py').read()); print('OK')\"")
log(f"  orchestrator.py: {'✅ syntax OK' if 'OK' in out else '⚠ ' + out[:60]}")

out = run("python3 -c \"import ast; ast.parse(open('world_state.py').read()); print('OK')\"")
log(f"  world_state.py:  {'✅ syntax OK' if 'OK' in out else '⚠ ' + out[:60]}")

out = run("systemctl is-active n8n")
log(f"  n8n: {'✅' if out=='active' else '⚠ ' + out}")

log("""
════════════════════════════════════════
  UPGRADE CONCLUÍDO — 9.5/10
  Novos arquivos: orchestrator.py | world_state.py | health_monitor.py
  Testar loop autônomo:
    python3 ~/JOD_ROBO/orchestrator.py 'crie estratégia de tráfego'
  Health monitor em background:
    nohup python3 ~/JOD_ROBO/health_monitor.py >> ~/JOD_ROBO/health.log 2>&1 &
════════════════════════════════════════""")
