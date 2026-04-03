#!/usr/bin/env python3
"""
JOD_ROBO — Robô-mãe v5.0 (10/10)
FASE 1: Auth + Health + Loop autônomo
FASE 2: Aprendizado por reforço + Paralelismo + World State
FASE 3: Auto-correção + Retry exponencial + JS fallback
"""
import asyncio, json, os, sqlite3, uuid, httpx, sys, logging, ast, io, contextlib
from datetime import datetime, timezone
from pathlib import Path
from groq import Groq
from dotenv import load_dotenv
import xmom_bus
import xmom_state
from xmom_semantic import feed_semantic_memory, search_semantic, semantic_context_for

load_dotenv(Path(__file__).resolve().parent / ".env")
logger   = logging.getLogger("ROBO_MAE")
client   = Groq(api_key=os.getenv("GROQ_API_KEY"))
DB_PATH  = Path(__file__).resolve().parent / "jod_robo.db"
MEMORY_PATH = Path(__file__).resolve().parent / "memory"
OUTPUT_PATH = Path(__file__).resolve().parent / "outputs"
MEMORY_PATH.mkdir(exist_ok=True)
OUTPUT_PATH.mkdir(exist_ok=True)

# ─── FACTORY ────────────────────────────────────────────────────────────────────
FACTORY_URL = "http://localhost:37777"
TRUST_TOKEN = os.getenv("JOD_TRUST_MANIFEST", "jod_robo_trust_2026_secure")
FACTORY_AGENTS    = ["agente_finalizador","agente_guardiao","agente_planner",
                     "agente_suporte_01","agente_browser","agente_memoria","agente_dados"]
FACTORY_TEMPLATES = ["support","executor","scheduler","analyzer","crawler"]

SQUADS = {
    "traffic-masters":     {"chief":"traffic-chief",   "keywords":["trafego","traffic","anuncio","ads","facebook ads","google ads","meta","campanha","cpa","roas","midia paga"]},
    "copy-squad":          {"chief":"copy-chief",      "keywords":["copy","copywriting","texto","headline","email","carta de vendas","persuasao","script","roteiro","vsl","landing page"]},
    "brand-squad":         {"chief":"brand-chief",     "keywords":["marca","brand","branding","posicionamento","identidade","logo","naming","arquetipo","brandbook","brand book","guia de marca","manual de marca","identidade visual","tom de voz"]},
    "data-squad":          {"chief":"data-chief",      "keywords":["dados","analytics","metricas","kpi","growth","retencao","churn","clv","ltv","cohort","north star","pmf"]},
    "design-squad":        {"chief":"design-chief",    "keywords":["design","ui","ux","interface","figma","prototipo","wireframe","design system"]},
    "hormozi-squad":       {"chief":"hormozi-chief",   "keywords":["oferta","offer","precificacao","preco","hormozi","grand slam","value stack","garantia","bonus"]},
    "storytelling":        {"chief":"story-chief",     "keywords":["historia","story","narrativa","storytelling","jornada","heroi","arco","campbell"]},
    "movement":            {"chief":"movement-chief",  "keywords":["movimento","proposito","missao","manifesto","ritual","simbolo"]},
    "cybersecurity":       {"chief":"cyber-chief",     "keywords":["seguranca","security","pentest","vulnerabilidade","hacking","owasp","incidente"]},
    "claude-code-mastery": {"chief":"claude-mastery-chief","keywords":["claude code","mcp","hooks","automacao","prompt engineering"]},
    "c-level-squad":       {"chief":"vision-chief",    "keywords":["estrategia","ceo","coo","cto","cmo","visao","okr","planejamento","fundraising","pitch"]},
    "advisory-board":      {"chief":"board-chair",     "keywords":["conselho","advisory","decisao","mental model","dalio","munger","thiel","naval","principios"]},
    "n8n-squad":           {"chief":"n8n-chief",       "keywords":["n8n","workflow","automacao","webhook","node","integracao","http request","schedule","trigger","code node","langchain","ai node","subworkflow","error handling","docker n8n","postgres n8n","redis n8n","queue mode","oauth","api integration","automatizar","criar workflow","novo workflow"]},
}

# Injeta squads extras do bus (ex: social-squad) sem duplicar
for _sq, _data in xmom_bus.SOCIAL_SQUAD.items():
    if _sq not in SQUADS:
        SQUADS[_sq] = _data

# ─── FASE 2: WORLD STATE ────────────────────────────────────────────────────────
STATE_PATH = Path(__file__).resolve().parent / "world_state.json"

def _load_state() -> dict:
    if STATE_PATH.exists():
        try: return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception: pass
    return {"sessions": {}, "decisions": [], "deliverables": [],
            "squad_preferences": {}, "created_at": datetime.now(timezone.utc).isoformat()}

def _save_state(state: dict):
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

def _update_world_state(session_id, squad, message, response, score=7.0):
    try:
        state = _load_state()
        if session_id not in state["sessions"]:
            state["sessions"][session_id] = {"turns": 0, "squads": [], "started": datetime.now(timezone.utc).isoformat()}
        sess = state["sessions"][session_id]
        sess["turns"] += 1
        sess["last_squad"] = squad
        if squad not in sess["squads"]: sess["squads"].append(squad)
        state["decisions"].append({"ts": datetime.now(timezone.utc).isoformat(),
                                   "session": session_id, "squad": squad,
                                   "score": score, "summary": message[:100]})
        state["decisions"] = state["decisions"][-100:]
        if squad not in state["squad_preferences"]:
            state["squad_preferences"][squad] = {"calls": 0, "avg_score": 7.0}
        pref = state["squad_preferences"][squad]
        pref["calls"] += 1
        pref["avg_score"] = (pref["avg_score"] * (pref["calls"] - 1) + score) / pref["calls"]
        if score >= 8.0:
            state["deliverables"].append({"ts": datetime.now(timezone.utc).isoformat(),
                                          "squad": squad, "score": score, "preview": response[:200]})
            state["deliverables"] = state["deliverables"][-50:]
        _save_state(state)
    except Exception as e:
        logger.warning(f"[WORLD_STATE] update erro: {e}")

def _get_world_context(session_id: str) -> str:
    try:
        state = _load_state()
        sess  = state["sessions"].get(session_id, {})
        prefs = state.get("squad_preferences", {})
        top   = sorted(prefs.items(), key=lambda x: x[1]["avg_score"], reverse=True)[:3]
        top_s = ", ".join([f"{sq}({d['avg_score']:.1f})" for sq, d in top])
        return f"Sessão {session_id}: {sess.get('turns',0)} turnos | Top squads: {top_s}"
    except Exception:
        return ""

# ─── FASE 2: AGENT PERFORMANCE (SQLite) ─────────────────────────────────────────
def _ensure_perf_table():
    try:
        conn = sqlite3.connect(DB_PATH)
        cur  = conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS agent_performance (
            squad TEXT PRIMARY KEY, total_calls INTEGER DEFAULT 0,
            total_score REAL DEFAULT 0, avg_score REAL DEFAULT 7.0, last_used TEXT)""")
        for sq in SQUADS:
            cur.execute("INSERT OR IGNORE INTO agent_performance (squad) VALUES (?)", (sq,))
        conn.commit(); conn.close()
    except Exception as e:
        logger.warning(f"[PERF] tabela erro: {e}")

_ensure_perf_table()

def _get_squad_perf() -> dict:
    try:
        conn = sqlite3.connect(DB_PATH)
        cur  = conn.cursor()
        cur.execute("SELECT squad, avg_score FROM agent_performance")
        rows = {r[0]: r[1] for r in cur.fetchall()}
        conn.close(); return rows
    except Exception:
        return {}

def _update_squad_perf(squad: str, score: float):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur  = conn.cursor()
        cur.execute("""INSERT INTO agent_performance (squad, total_calls, total_score, avg_score, last_used)
            VALUES (?, 1, ?, ?, ?)
            ON CONFLICT(squad) DO UPDATE SET
                total_calls = total_calls + 1,
                total_score = total_score + excluded.total_score,
                avg_score   = (total_score + excluded.total_score) / (total_calls + 1),
                last_used   = excluded.last_used""",
            (squad, score, score, datetime.now(timezone.utc).isoformat()))
        conn.commit(); conn.close()
    except Exception as e:
        logger.warning(f"[PERF] update erro: {e}")

# ─── FASE 3: FACTORY CALL COM RETRY EXPONENCIAL ─────────────────────────────────
async def factory_call(method, path, payload=None, retries=3):
    headers = {"Content-Type": "application/json", "x-trust-token": TRUST_TOKEN,
               "x-request-id": f"rm-{str(uuid.uuid4())[:8]}",
               "x-idempotency-key": str(uuid.uuid4())}
    last_err = None
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=15.0) as http:
                if method == "POST":
                    r = await http.post(f"{FACTORY_URL}{path}", headers=headers, json=payload)
                else:
                    r = await http.get(f"{FACTORY_URL}{path}", headers=headers)
            if r.status_code < 500:
                return r.json()
            last_err = f"HTTP {r.status_code}"
        except Exception as e:
            last_err = str(e)
        await asyncio.sleep(2 ** attempt)  # backoff: 1s, 2s, 4s
    return {"error": f"factory_call falhou após {retries} tentativas: {last_err}"}

async def factory_wait(task_id, tries=20):
    for i in range(tries):
        await asyncio.sleep(0.5 + i * 0.1)
        try:
            r = await factory_call("GET", f"/tasks/{task_id}")
            if r.get("status") in ("succeeded", "failed", "rolled_back"): return r
        except: pass
    return {"status": "timeout"}

async def factory_list():
    try: return await factory_call("GET", "/agents")
    except: return []

async def factory_create(template, agent_id, name):
    r = await factory_call("POST", "/agents/create-from-template",
        {"action_type": "create_agent_from_template",
         "parameters": {"template_name": template, "new_agent_id": agent_id, "name": name}})
    return await factory_wait(r.get("task_id")) if r.get("task_id") else r

async def factory_activate(agent_id):
    r = await factory_call("POST", "/agents/activate",
        {"action_type": "activate_agent", "parameters": {"agent_id": agent_id}})
    return await factory_wait(r.get("task_id")) if r.get("task_id") else r

async def factory_validate(agent_id):
    r = await factory_call("POST", "/agents/validate",
        {"action_type": "validate_agent", "parameters": {"agent_id": agent_id}})
    return await factory_wait(r.get("task_id")) if r.get("task_id") else r

# ─── BROWSER ────────────────────────────────────────────────────────────────────
async def browser_navigate(url: str) -> dict:
    try:
        import importlib.util
        paths = [
            Path(__file__).resolve().parent / "agente_browser.py",
            Path(__file__).resolve().parent / "agents" / "agente_browser" / "main.py",
        ]
        browser_path = next((p for p in paths if p.exists()), None)
        if not browser_path: return {"error": "agente_browser não encontrado", "url": url}
        spec = importlib.util.spec_from_file_location("agente_browser", browser_path)
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return await mod.navigate(url)
    except Exception as e:
        return {"error": str(e), "url": url}

async def browser_screenshot(url: str) -> dict:
    try:
        import importlib.util
        paths = [
            Path(__file__).resolve().parent / "agente_browser.py",
            Path(__file__).resolve().parent / "agents" / "agente_browser" / "main.py",
        ]
        browser_path = next((p for p in paths if p.exists()), None)
        if not browser_path: return {"error": "agente_browser não encontrado"}
        spec = importlib.util.spec_from_file_location("agente_browser", browser_path)
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return await mod.screenshot(url)
    except Exception as e:
        return {"error": str(e)}

# ─── OUTPUT ─────────────────────────────────────────────────────────────────────
# Diretório global de outputs (fora do repo)
GLOBAL_OUTPUT_PATH = Path("/home/jod_robo/outputs")
GLOBAL_OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

def save_output(filename: str, content: str) -> str:
    path = OUTPUT_PATH / filename
    with open(path, "w", encoding="utf-8") as f: f.write(content)
    return str(path)

async def _tool_create_post(message: str, session_id: str) -> dict:
    """Gera post social via LLM, salva em /home/jod_robo/outputs/ e retorna path."""
    squad_name = "social-squad"
    mem        = load_memory(session_id)
    prompt     = f"Crie um post otimizado para Instagram (com emojis, hashtags, call-to-action):\n{message}"
    content    = await consult(squad_name, prompt, mem)
    ts         = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename   = f"post_{ts}.md"
    out_path   = GLOBAL_OUTPUT_PATH / filename
    out_path.write_text(content, encoding="utf-8")
    save_memory(session_id, squad_name, SQUADS[squad_name]["chief"], message, content)
    return {
        "squad":   squad_name,
        "chief":   SQUADS[squad_name]["chief"],
        "path":    str(out_path),
        "content": content,
    }

# ─── GAP 1: SANDBOX PYTHON ──────────────────────────────────────────────────────
_SAFE_BUILTINS: dict = {
    "print": print, "len": len, "range": range, "enumerate": enumerate,
    "zip": zip, "map": map, "filter": filter, "sorted": sorted, "reversed": reversed,
    "sum": sum, "min": min, "max": max, "abs": abs, "round": round,
    "int": int, "float": float, "str": str, "bool": bool, "list": list,
    "dict": dict, "set": set, "tuple": tuple, "type": type,
    "isinstance": isinstance, "repr": repr, "format": format,
    "True": True, "False": False, "None": None,
    "Exception": Exception, "ValueError": ValueError, "TypeError": TypeError,
    "KeyError": KeyError, "IndexError": IndexError,
}

def _sandbox_check(code: str) -> list[str]:
    """Retorna lista de violações de segurança. Vazio = seguro."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [f"SyntaxError: {e}"]
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            violations.append(f"Linha {node.lineno}: import proibido no sandbox")
        if isinstance(node, ast.Call):
            func = node.func
            name = (func.id if isinstance(func, ast.Name) else
                    func.attr if isinstance(func, ast.Attribute) else "")
            if name in {"open", "exec", "eval", "compile", "__import__",
                        "breakpoint", "globals", "locals", "vars", "dir",
                        "getattr", "setattr", "delattr"}:
                violations.append(f"Linha {getattr(node, 'lineno', '?')}: chamada proibida '{name}'")
    return violations

async def _tool_run_python(code: str, session_id: str) -> dict:
    """Executa Python em sandbox restrito (sem imports, timeout 5s). GAP 1."""
    violations = _sandbox_check(code)
    if violations:
        return {"ok": False, "error": "\n".join(violations), "stdout": "", "squad": "sandbox"}

    stdout_buf = io.StringIO()
    ns = {"__builtins__": _SAFE_BUILTINS}
    err: list[str] = []

    def _exec():
        try:
            with contextlib.redirect_stdout(stdout_buf):
                exec(compile(code, "<sandbox>", "exec"), ns)  # noqa: S102
        except Exception as e:
            err.append(f"{type(e).__name__}: {e}")

    loop = asyncio.get_event_loop()
    try:
        await asyncio.wait_for(loop.run_in_executor(None, _exec), timeout=5.0)
    except asyncio.TimeoutError:
        return {"ok": False, "error": "Timeout (5s)", "stdout": stdout_buf.getvalue(), "squad": "sandbox"}

    if err:
        return {"ok": False, "error": err[0], "stdout": stdout_buf.getvalue(), "squad": "sandbox"}
    return {"ok": True, "stdout": stdout_buf.getvalue(), "error": "", "squad": "sandbox"}

# ─── GAP 4: TOOLS ADICIONAIS ─────────────────────────────────────────────────────
async def _tool_send_webhook(url: str, payload: dict, session_id: str) -> dict:
    """Envia HTTP POST a uma URL com payload JSON."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.post(url, json=payload,
                             headers={"Content-Type": "application/json",
                                      "x-source": "xmom-v5"})
        return {"ok": True, "status": r.status_code, "body": r.text[:500], "squad": "tools"}
    except Exception as e:
        return {"ok": False, "error": str(e), "squad": "tools"}

async def _tool_read_file(path: str, session_id: str) -> dict:
    """Lê arquivo restrito a /home/jod_robo/outputs/ e XMOM_V5/outputs/."""
    p = Path(path).resolve()
    allowed = [GLOBAL_OUTPUT_PATH.resolve(), OUTPUT_PATH.resolve()]
    if not any(str(p).startswith(str(a)) for a in allowed):
        return {"ok": False, "error": f"Acesso negado: {path}", "content": "", "squad": "tools"}
    try:
        content = p.read_text(encoding="utf-8")
        return {"ok": True, "content": content[:4000], "path": str(p), "squad": "tools"}
    except Exception as e:
        return {"ok": False, "error": str(e), "content": "", "squad": "tools"}

async def _tool_write_file(path: str, content: str, session_id: str) -> dict:
    """Escreve arquivo restrito a /home/jod_robo/outputs/."""
    p = Path(path)
    if not p.is_absolute():
        p = GLOBAL_OUTPUT_PATH / p
    p = p.resolve()
    if not str(p).startswith(str(GLOBAL_OUTPUT_PATH.resolve())):
        return {"ok": False, "error": f"Acesso negado: apenas outputs/", "squad": "tools"}
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"ok": True, "path": str(p), "bytes": len(content.encode()), "squad": "tools"}
    except Exception as e:
        return {"ok": False, "error": str(e), "squad": "tools"}

async def _tool_call_api(url: str, method: str, headers: dict,
                         body: dict | None, session_id: str) -> dict:
    """Chama API externa com método, headers e body customizados."""
    method = method.upper()
    try:
        async with httpx.AsyncClient(timeout=15.0) as c:
            if method == "GET":
                r = await c.get(url, headers=headers)
            elif method == "POST":
                r = await c.post(url, json=body, headers=headers)
            elif method == "PUT":
                r = await c.put(url, json=body, headers=headers)
            elif method == "DELETE":
                r = await c.delete(url, headers=headers)
            else:
                return {"ok": False, "error": f"Método não suportado: {method}", "squad": "tools"}
        try:
            resp_body = r.json()
        except Exception:
            resp_body = r.text[:1000]
        return {"ok": r.status_code < 400, "status": r.status_code,
                "body": resp_body, "squad": "tools"}
    except Exception as e:
        return {"ok": False, "error": str(e), "squad": "tools"}

# ─── GAP 5: ORQUESTRAÇÃO MULTI-AGENTE ────────────────────────────────────────────
async def multi_squad_consult(message: str, session_memory: list,
                               squads_list: list[str]) -> dict:
    """Consulta múltiplos squads em paralelo (orquestração). GAP 5."""
    valid_squads = [sq for sq in squads_list if sq in SQUADS][:4]
    if not valid_squads:
        valid_squads = ["c-level-squad", "advisory-board"]

    tasks     = [consult(sq, message, session_memory) for sq in valid_squads]
    results   = await asyncio.gather(*tasks, return_exceptions=True)
    combined  = {}
    event_ids = []

    for sq, res in zip(valid_squads, results):
        if isinstance(res, str) and len(res.strip()) > 20:
            combined[sq] = res
            # Publica resultado como evento no bus
            eid = xmom_bus.publish_task(
                "squad_result",
                {"squad": sq, "message": message[:100], "result_preview": res[:200]},
                source=sq,
            )
            event_ids.append(eid)
            xmom_bus.complete_task(eid, res[:300])

    parts = [f"### {sq.replace('-',' ').title()}\n{resp}"
             for sq, resp in combined.items()]
    return {
        "squad": "multi-squad",
        "chief": "orchestrator",
        "response": "\n\n---\n\n".join(parts) if parts else "Nenhuma resposta disponível.",
        "squads_consulted": list(combined.keys()),
        "event_ids": event_ids,
    }

# ─── DETECT INTENT ──────────────────────────────────────────────────────────────
def detect_intent(message: str) -> dict:
    ml = message.lower().strip()

    nav_patterns = ["abra o site","navegar para","acesse o site","abre o site","navega para","visitar","abrir url","navegar url"]
    for p in nav_patterns:
        if p in ml:
            words = message.split()
            url   = next((w for w in words if w.startswith("http")), None)
            if not url: url = next((w for w in words if "." in w and len(w) > 4), None)
            if url and not url.startswith("http"): url = "https://" + url
            return {"intent": "browser_navigate", "url": url or "https://example.com"}

    shot_patterns = ["screenshot","print da tela","captura de tela","tire um print","foto do site"]
    for p in shot_patterns:
        if p in ml:
            words = message.split()
            url   = next((w for w in words if w.startswith("http")), None)
            return {"intent": "browser_screenshot", "url": url or "https://example.com"}

    if any(p in ml for p in ["liste os agentes","listar agentes","agentes ativos","quais agentes","ver agentes"]):
        return {"intent": "factory_list"}
    for p in ["ative o","ativar o","ative agente","ativar agente"]:
        if p in ml:
            for a in FACTORY_AGENTS:
                if a in ml: return {"intent": "factory_activate", "agent_id": a}
            return {"intent": "factory_activate", "agent_id": None}
    for p in ["valide o","validar o","valide agente","validar agente"]:
        if p in ml:
            for a in FACTORY_AGENTS:
                if a in ml: return {"intent": "factory_validate", "agent_id": a}
            return {"intent": "factory_validate", "agent_id": None}
    for p in ["crie um agente","criar agente","novo agente","criar um agente"]:
        if p in ml:
            template = next((t for t in FACTORY_TEMPLATES if t in ml), "executor")
            agent_id = f"agente_{str(uuid.uuid4())[:6]}"
            return {"intent": "factory_create", "template": template, "agent_id": agent_id, "name": agent_id}

    n8n_create = ["crie um workflow","criar workflow","novo workflow","automatizar com n8n","criar automacao no n8n"]
    for p in n8n_create:
        if p in ml: return {"intent": "n8n_create", "description": message}
    if any(p in ml for p in ["liste os workflows","listar workflows","ver workflows"]):
        return {"intent": "n8n_list"}
    if any(p in ml for p in ["ative o workflow","ativar workflow"]):
        wf_id = next((w for w in message.split() if w.isalnum() and len(w) > 5), None)
        return {"intent": "n8n_activate", "workflow_id": wf_id}
    for p in ["salve","salvar","gere um arquivo","criar arquivo","exportar","save"]:
        if p in ml: return {"intent": "save_file"}

    # GAP 1: sandbox python
    for p in ["execute python", "run python", "executar python", "rodar código",
              "execute código", "python sandbox", "run code"]:
        if p in ml:
            # Extrai bloco de código (``` ou tudo após o trigger)
            if "```" in message:
                raw = message[message.find("```"):]
                raw = raw.strip("`").lstrip("python").strip()
            else:
                raw = message[message.lower().find(p) + len(p):].strip()
            return {"intent": "tool_run_python", "code": raw}

    # GAP 4: file tools
    for p in ["leia o arquivo", "ler arquivo", "read file", "abrir arquivo"]:
        if p in ml:
            words = message.split()
            path  = next((w for w in words if "/" in w or w.endswith(".md") or w.endswith(".txt")), "")
            return {"intent": "tool_read_file", "path": path}

    for p in ["escreva no arquivo", "write file", "salvar em arquivo", "criar arquivo em"]:
        if p in ml:
            words = message.split()
            path  = next((w for w in words if "/" in w or w.endswith(".md")), "output.md")
            return {"intent": "tool_write_file", "path": path, "content": message}

    for p in ["envie webhook", "send webhook", "disparar webhook", "webhook para"]:
        if p in ml:
            words = message.split()
            url   = next((w for w in words if w.startswith("http")), "")
            return {"intent": "tool_send_webhook", "url": url, "payload": {"message": message}}

    for p in ["chame a api", "call api", "fazer requisição", "request para", "api call"]:
        if p in ml:
            words  = message.split()
            url    = next((w for w in words if w.startswith("http")), "")
            method = next((w.upper() for w in words if w.upper() in {"GET","POST","PUT","DELETE"}), "GET")
            return {"intent": "tool_call_api", "url": url, "method": method,
                    "headers": {}, "body": None}

    # GAP 5: orquestração multi-squad
    for p in ["orquestre", "distribua para", "multi-squad", "consulte todos",
              "pergunte para vários", "paralelo com", "delega para"]:
        if p in ml:
            # Detecta squads mencionados
            mentioned = [sq for sq in SQUADS if sq.replace("-"," ") in ml or sq in ml]
            if not mentioned:
                mentioned = ["copy-squad", "brand-squad", "c-level-squad"]
            return {"intent": "orchestrate", "squads": mentioned[:3], "message": message}

    # Delega ao bus local para intents extras (create_post, etc.)
    bus_intent = xmom_bus.detect_intent_local(ml)
    if bus_intent:
        return bus_intent

    return {"intent": "consult"}

# ─── EXECUTE INTENT ─────────────────────────────────────────────────────────────
async def execute_intent(intent: dict, message: str, session_id: str) -> dict:
    i = intent["intent"]

    if i == "factory_list":
        agents = await factory_list()
        lines  = [f"  - {a['id']} [{a['status']}]" for a in agents] if agents else ["  Factory indisponível"]
        return {"squad": "factory", "chief": "factory", "response": "Agentes no Factory:\n" + "\n".join(lines)}

    elif i == "factory_activate":
        aid = intent.get("agent_id")
        if not aid: return {"squad": "factory", "chief": "factory", "response": "Qual agente quer ativar?"}
        r = await factory_activate(aid)
        return {"squad": "factory", "chief": "factory", "response": f"Agente `{aid}` → **{r.get('status','?')}**"}

    elif i == "factory_validate":
        aid = intent.get("agent_id")
        if not aid: return {"squad": "factory", "chief": "factory", "response": "Qual agente quer validar?"}
        r = await factory_validate(aid)
        return {"squad": "factory", "chief": "factory", "response": f"Agente `{aid}` → **{r.get('status','?')}**"}

    elif i == "factory_create":
        r = await factory_create(intent["template"], intent["agent_id"], intent["name"])
        return {"squad": "factory", "chief": "factory",
                "response": f"Agente `{intent['agent_id']}` (template: {intent['template']}) → **{r.get('status','?')}**"}

    elif i == "browser_navigate":
        url    = intent.get("url", "https://example.com")
        result = await browser_navigate(url)
        if "error" in result:
            return {"squad": "browser", "chief": "agente_browser", "response": f"Erro ao navegar: {result['error']}"}
        return {"squad": "browser", "chief": "agente_browser",
                "response": f"**Navegação concluída**\nURL: {result.get('url')}\nTítulo: {result.get('title')}\n\n{result.get('content','')[:500]}"}

    elif i == "browser_screenshot":
        url    = intent.get("url", "https://example.com")
        result = await browser_screenshot(url)
        if "error" in result:
            return {"squad": "browser", "chief": "agente_browser", "response": f"Erro no screenshot: {result['error']}"}
        return {"squad": "browser", "chief": "agente_browser", "response": f"Screenshot: `{result.get('screenshot')}`"}

    elif i == "n8n_create":
        try:
            import importlib.util
            n8n_path = next((p for p in [
                Path(__file__).resolve().parent / "agente_n8n.py",
                Path(__file__).resolve().parent / "agents" / "agente_n8n" / "main.py",
            ] if p.exists()), None)
            if not n8n_path: raise FileNotFoundError("agente_n8n.py não encontrado")
            spec = importlib.util.spec_from_file_location("agente_n8n", n8n_path)
            mod  = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
            result = await mod.create_from_description(intent.get("description", "workflow"))
            return {"squad": "n8n-squad", "chief": "n8n-chief",
                    "response": f"✅ Workflow criado!\n**Nome:** {result['name']}\n**ID:** {result['id']}\nAcesse: http://localhost:5678"}
        except Exception as e:
            return {"squad": "n8n-squad", "chief": "n8n-chief", "response": f"Erro ao criar workflow: {e}"}

    elif i == "n8n_list":
        try:
            import importlib.util
            n8n_path = Path(__file__).resolve().parent / "agente_n8n.py"
            spec = importlib.util.spec_from_file_location("agente_n8n", n8n_path)
            mod  = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
            workflows = await mod.list_workflows()
            if not workflows: return {"squad": "n8n-squad", "chief": "n8n-chief", "response": "Nenhum workflow encontrado."}
            lines = [f"  - [{w['id']}] {w['name']} (ativo: {w['active']})" for w in workflows]
            return {"squad": "n8n-squad", "chief": "n8n-chief", "response": "Workflows:\n" + "\n".join(lines)}
        except Exception as e:
            return {"squad": "n8n-squad", "chief": "n8n-chief", "response": f"Erro: {e}"}

    elif i == "create_post":
        result = await _tool_create_post(intent.get("message", message), session_id)
        return {
            "squad":    result["squad"],
            "chief":    result["chief"],
            "response": f"Post criado e salvo!\n`{result['path']}`\n\n---\n{result['content']}",
        }

    elif i == "save_file":
        mem        = load_memory(session_id)
        squad_name, score = route(message)
        if score == 0: squad_name, _ = xmom_bus.route_local(message, SQUADS)
        content  = await consult(squad_name, message, mem)
        ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{squad_name}_{ts}.md"
        path     = save_output(filename, content)
        save_memory(session_id, squad_name, SQUADS[squad_name]["chief"], message, content)
        return {"squad": squad_name, "chief": SQUADS[squad_name]["chief"],
                "response": f"Arquivo salvo:\n`{path}`\n\n---\n{content}"}

    # ── GAP 1 ────────────────────────────────────────────────────────────────────
    elif i == "tool_run_python":
        code = intent.get("code", "")
        if not code.strip():
            return {"squad": "sandbox", "chief": "sandbox", "response": "Nenhum código para executar."}
        res = await _tool_run_python(code, session_id)
        status = "✅ Executado" if res["ok"] else "❌ Erro"
        return {"squad": "sandbox", "chief": "sandbox",
                "response": f"{status}\n\n**stdout:**\n```\n{res['stdout']}\n```\n\n**erro:** {res['error']}"}

    # ── GAP 4 ────────────────────────────────────────────────────────────────────
    elif i == "tool_read_file":
        path = intent.get("path", "")
        if not path:
            return {"squad": "tools", "chief": "tools", "response": "Informe o caminho do arquivo."}
        res = await _tool_read_file(path, session_id)
        if not res["ok"]:
            return {"squad": "tools", "chief": "tools", "response": f"❌ {res['error']}"}
        return {"squad": "tools", "chief": "tools",
                "response": f"📄 `{res['path']}`\n\n```\n{res['content']}\n```"}

    elif i == "tool_write_file":
        path    = intent.get("path", "output.md")
        content = intent.get("content", message)
        res     = await _tool_write_file(path, content, session_id)
        if not res["ok"]:
            return {"squad": "tools", "chief": "tools", "response": f"❌ {res['error']}"}
        return {"squad": "tools", "chief": "tools",
                "response": f"✅ Arquivo gravado: `{res['path']}` ({res['bytes']} bytes)"}

    elif i == "tool_send_webhook":
        url     = intent.get("url", "")
        payload = intent.get("payload", {"message": message})
        if not url:
            return {"squad": "tools", "chief": "tools", "response": "URL do webhook não informada."}
        res = await _tool_send_webhook(url, payload, session_id)
        if not res["ok"]:
            return {"squad": "tools", "chief": "tools", "response": f"❌ Webhook falhou: {res.get('error')}"}
        return {"squad": "tools", "chief": "tools",
                "response": f"✅ Webhook enviado → HTTP {res['status']}\n{res.get('body','')}"}

    elif i == "tool_call_api":
        url    = intent.get("url", "")
        method = intent.get("method", "GET")
        if not url:
            return {"squad": "tools", "chief": "tools", "response": "URL da API não informada."}
        res = await _tool_call_api(url, method, intent.get("headers", {}),
                                    intent.get("body"), session_id)
        status = "✅" if res["ok"] else "❌"
        return {"squad": "tools", "chief": "tools",
                "response": f"{status} {method} {url} → {res.get('status','?')}\n```json\n{json.dumps(res.get('body',''), ensure_ascii=False, indent=2)[:800]}\n```"}

    # ── GAP 5 ────────────────────────────────────────────────────────────────────
    elif i == "orchestrate":
        mem    = load_memory(session_id)
        msg    = intent.get("message", message)
        squads = intent.get("squads", ["copy-squad", "brand-squad"])
        result = await multi_squad_consult(msg, mem, squads)
        save_memory(session_id, result["squad"], result["chief"], message, result["response"])
        return result

    return None

# ─── BANCO ──────────────────────────────────────────────────────────────────────
def get_agent_data(name):
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.execute("SELECT name,squad,role,tier,description,capabilities,persona FROM agents WHERE name=?", (name,))
    row  = cur.fetchone(); conn.close()
    if not row: return {}
    return {"name": row[0], "squad": row[1], "role": row[2], "tier": row[3],
            "description": row[4], "capabilities": row[5], "persona": row[6]}

def get_specialists(squad_name):
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.execute("SELECT name,description FROM agents WHERE squad=? AND tier>0 ORDER BY tier,name", (squad_name,))
    rows = cur.fetchall(); conn.close()
    return rows

# ─── FASE 1+2: SAVE MEMORY COM SCORE E PERF ─────────────────────────────────────
def save_memory(session_id, squad, agent, user_msg, response, score=7.0):
    with open(MEMORY_PATH / "conversations.jsonl", "a") as f:
        f.write(json.dumps({
            "session_id": session_id,
            "timestamp":  datetime.now(timezone.utc).isoformat(),
            "squad": squad, "agent": agent,
            "user": user_msg, "response": response, "score": score
        }, ensure_ascii=False) + "\n")
    _update_squad_perf(squad, score)
    _update_world_state(session_id, squad, user_msg, response, score)
    # GAP 2: alimenta pipeline de memória semântica
    try:
        feed_semantic_memory(session_id, squad, response, score)
    except Exception as _e:
        logger.warning(f"[SEMANTIC] feed erro: {_e}")

def load_memory(session_id, limit=4):
    mf = MEMORY_PATH / "conversations.jsonl"
    if not mf.exists(): return []
    entries = []
    for line in open(mf):
        try:
            e = json.loads(line)
            if e.get("session_id") == session_id: entries.append(e)
        except: pass
    return entries[-limit:]

# ─── FASE 2: ROTEAMENTO COM DESEMPATE POR PERFORMANCE ───────────────────────────
def route(message):
    ml     = message.lower()
    scores = {sq: sum(1 for kw in data["keywords"] if kw in ml) for sq, data in SQUADS.items()}
    scores = {k: v for k, v in scores.items() if v > 0}
    if not scores: return "advisory-board", 0
    perf    = _get_squad_perf()
    max_kw  = max(scores.values())
    tied    = [sq for sq, v in scores.items() if v == max_kw]
    best    = max(tied, key=lambda sq: perf.get(sq, 7.0)) if len(tied) > 1 else tied[0]
    return best, scores[best]

async def route_llm(message):
    kw_hint = "\n".join([f"- {k}: {', '.join(data['keywords'][:4])}" for k, data in SQUADS.items()])
    try:
        r  = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": (
                    "Classificador de intenções. Retorne APENAS o slug exato do squad mais adequado.\n"
                    "Slugs válidos e keywords:\n" + kw_hint + "\n"
                    "REGRA: mensagens curtas, pings, saudações, testes → c-level-squad.\n"
                    "Retorne SOMENTE o slug, sem explicação, sem markdown.")},
                {"role": "user", "content": message}
            ],
            temperature=0.0, max_tokens=24
        )
        sq = r.choices[0].message.content.strip().lower().strip("`")
        if sq in SQUADS: return sq
        for slug in SQUADS:
            if slug in sq or sq in slug: return slug
    except Exception as e:
        logger.warning(f"[ROUTE_LLM] erro: {e}")
    return "c-level-squad" if len(message.split()) <= 3 else "advisory-board"

# ─── OFFLINE FALLBACK ────────────────────────────────────────────────────────────
_FALLBACK_TEMPLATES = {
    "traffic-masters":     "Para tráfego pago, foque em testar criativos com CTR > 2%, otimize para conversão e escale o que funciona. Verifique: audiência, oferta, copy e landing page.",
    "copy-squad":          "Copy eficaz: headline que promete resultado específico, prova social, oferta irresistível com garantia, CTA claro. Use a fórmula AIDA ou PAS.",
    "brand-squad":         "Branding sólido: arquétipo definido, posicionamento único, identidade visual consistente, tom de voz autêntico e mensagem que ressoa com seu cliente ideal.",
    "data-squad":          "Análise de dados: defina sua North Star Metric, construa funis de conversão, monitore cohorts de retenção e tome decisões baseadas em dados, não intuição.",
    "design-squad":        "Design centrado no usuário: clareza antes de beleza, hierarquia visual clara, consistência com design system, feedback e testes com usuários reais.",
    "hormozi-squad":       "Oferta irresistível: aumente o valor percebido (resultado + velocidade + facilidade), remova o risco com garantia, empilhe bônus relevantes.",
    "storytelling":        "Narrativa poderosa: herói relatable + problema real + mentor guia + plano claro + chamado à ação. Use a jornada do herói de Joseph Campbell.",
    "movement":            "Movimento com propósito: manifesto claro, rituais que unem, símbolos que identificam, missão que transcende o produto.",
    "cybersecurity":       "Segurança em camadas: autenticação forte (MFA), princípio do mínimo privilégio, monitoramento contínuo, plano de resposta a incidentes.",
    "claude-code-mastery": "Claude Code: use hooks para automação, MCP servers para extensibilidade, slash commands para produtividade, e CLAUDE.md para contexto persistente.",
    "c-level-squad":       "Estratégia executiva: defina OKRs claros, alinhe time em torno da visão, tome decisões com dados, pivote rápido quando necessário.",
    "advisory-board":      "Decisão sábia: inverta riscos (o que pode dar errado?), aplique modelos mentais (segunda ordem, inversão, círculo de competência), aja com margem de segurança.",
    "n8n-squad":           "n8n: use HTTP Request nodes para integrar APIs, Code nodes para lógica complexa, webhooks para eventos em tempo real, Error Trigger para tratamento de falhas.",
    "social-squad":        "Post de impacto: hook nas primeiras 3 palavras, valor real no conteúdo, call-to-action específico, hashtags estratégicas (5-10 relevantes).",
}

def _local_fallback(squad_name: str, message: str) -> str:
    """Resposta offline sem LLM — usado quando Groq e OpenRouter falham."""
    base = _FALLBACK_TEMPLATES.get(squad_name, _FALLBACK_TEMPLATES["advisory-board"])
    topic = " ".join(message.split()[:8]) if message else "seu objetivo"
    return (f"[Modo Offline] Resposta baseada em conhecimento local do {squad_name}:\n\n"
            f"{base}\n\n"
            f"Para '{topic}', aplique esses princípios ao seu contexto específico. "
            f"Reconecte a internet ou verifique as chaves de API para respostas personalizadas.")

# ─── CONSULTA LLM ────────────────────────────────────────────────────────────────
async def consult(squad_name, message, session_memory):
    chief_name   = SQUADS[squad_name]["chief"]
    chief        = get_agent_data(chief_name)
    specialists  = get_specialists(squad_name)
    spec_list    = "\n".join([f"- {n}: {d}" for n, d in specialists]) if specialists else "nenhum"

    brandbook = ""
    if squad_name == "brand-squad":
        brandbook = """
BRANDBOOK — fluxo em 6 fases:
1. archetype-consultant → arquétipo e personalidade
2. jean-noel-kapferer → Identity Prism (6 facetas)
3. al-ries → posicionamento e tagline
4. alina-wheeler → identidade visual completa
5. donald-miller → BrandScript e messaging
6. naming-strategist + domain-scout → nome e domínio
Para SALVAR: diga 'salve o brandbook'."""

    n8n_expert = ""
    if squad_name == "n8n-squad":
        n8n_expert = """
VOCÊ É UM N8N EXPERT FAIXA PRETA. Domínio completo de:
JS/expressões, arquitetura escalável, HTTP/webhooks, infraestrutura Docker,
IA + LangChain, visão de negócio e ROI de automação.
Para criar workflow real: 'crie um workflow [descrição]'"""

    system = f"""Você é {chief.get('name','chief').replace('-',' ').title()}.
{chief.get('persona','')}
{chief.get('description','')}

ESPECIALISTAS REAIS (use APENAS estes nomes, NUNCA invente):
{spec_list}{brandbook}{n8n_expert}

CAPACIDADES: 'abra o site X' | 'screenshot X' | 'salve [resultado]' | 'liste os agentes'
REGRAS: Cite apenas nomes da lista. Responda em português. Seja direto e acionável."""

    msgs = [{"role": "system", "content": system}]
    for mem in session_memory:
        msgs.append({"role": "user",      "content": mem["user"]})
        msgs.append({"role": "assistant", "content": mem["response"]})
    msgs.append({"role": "user", "content": f"{message}\n\n[ESPECIALISTAS]: {spec_list}"})

    try:
        r=client.chat.completions.create(model="llama-3.3-70b-versatile",messages=msgs,temperature=0.7,max_tokens=1024)
        return r.choices[0].message.content.strip()
    except Exception as _e:
        logger.warning(f"[CB] Groq falhou: {_e} -> OpenRouter")
    try:
        r=_or_client().chat.completions.create(model="openai/gpt-3.5-turbo",messages=msgs,max_tokens=1024)
        return r.choices[0].message.content.strip()
    except Exception as _e2:
        logger.warning(f"[CB] OpenRouter falhou: {_e2} -> local fallback")
    return _local_fallback(squad_name, message)

# ─── FASE 2: CONSULT PARALELO ────────────────────────────────────────────────────
async def consult_parallel(squad_name, message, session_memory, n=2):
    """Executa n consultas em paralelo, retorna a de maior qualidade."""
    if n <= 1: return await consult(squad_name, message, session_memory)
    hints   = ["", " Seja direto e acionável.", " Inclua exemplos práticos e números."]
    tasks   = [consult(squad_name, message + hints[i % len(hints)], session_memory) for i in range(n)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    valid   = [r for r in results if isinstance(r, str) and len(r) > 50]
    return max(valid, key=len) if valid else await consult(squad_name, message, session_memory)

# ─── FASE 1: AVALIADOR DE QUALIDADE INTERNO ──────────────────────────────────────
async def evaluate_output(objective: str, output: str, squad: str) -> dict:
    prompt = f"""Avalie o output em relação ao objetivo. Retorne APENAS JSON válido:
{{"score": 8, "reason": "motivo", "improvement": "o que melhorar"}}
Score 0-10. 10=perfeito, 7=aceitável, <7=insuficiente.
OBJETIVO: {objective}
SQUAD: {squad}
OUTPUT: {output[:1200]}"""
    try:
        r   = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1, max_tokens=128)
        raw = r.choices[0].message.content.strip()
        for fence in ["```json", "```"]: raw = raw.removeprefix(fence).removesuffix(fence).strip()
        return json.loads(raw)
    except Exception:
        return {"score": 7, "reason": "avaliação indisponível", "improvement": ""}

# ─── PROCESSO PRINCIPAL ──────────────────────────────────────────────────────────
async def process(message, session_id, force_squad=None):
    # 1. Intenção de execução
    intent = detect_intent(message)
    if intent["intent"] != "consult":
        result = await execute_intent(intent, message, session_id)
        if result:
            save_memory(session_id, result["squad"], result["chief"], message, result["response"])
            return result

    # 2. Roteamento
    if force_squad and force_squad in SQUADS:
        squad_name = force_squad
    else:
        squad_name, score = route(message)
        if score == 0: squad_name, _ = xmom_bus.route_local(message, SQUADS)

    # 3. Consulta paralela + contexto semântico
    mem      = load_memory(session_id)
    sem_ctx  = semantic_context_for(message)
    aug_msg  = message + (f"\n\n[CONTEXTO RELEVANTE]\n{sem_ctx}" if sem_ctx else "")
    response = await consult_parallel(squad_name, aug_msg, mem, n=2)

    # 4. FASE 3: Auto-correção — resposta vazia → squad alternativo (bus local)
    if len(response.strip()) < 80:
        alt, _ = xmom_bus.route_local(message, SQUADS)
        if alt != squad_name and alt in SQUADS:
            alt_response = await consult(alt, message, mem)
            if len(alt_response.strip()) > len(response.strip()):
                squad_name = alt
                response   = alt_response

    # 5. GAP 6: evaluate_output — score < 7 dispara reexecução automática (max 1 retry)
    eval_result = await evaluate_output(message, response, squad_name)
    score       = eval_result.get("score", 7.0)
    if score < 7:
        logger.info(f"[EVAL] score={score} < 7 → retry com improvement hint")
        improvement = eval_result.get("improvement", "")
        retry_msg   = f"{message}\n\n[MELHORIA SOLICITADA]: {improvement}" if improvement else message
        retry_resp  = await consult(squad_name, retry_msg, mem)
        retry_eval  = await evaluate_output(message, retry_resp, squad_name)
        if retry_eval.get("score", 7.0) > score:
            response = retry_resp
            score    = retry_eval.get("score", score)

    # 6. Salva com score real
    save_memory(session_id, squad_name, SQUADS[squad_name]["chief"], message, response, score)
    return {"squad": squad_name, "chief": SQUADS[squad_name]["chief"],
            "response": response, "eval_score": score}

# ─── CLI ────────────────────────────────────────────────────────────────────────
async def chat():
    session_id = str(uuid.uuid4())[:8]
    print(f"\n{'='*60}\n  ELI v5.0 | Sessão {session_id}\n{'='*60}\n")
    while True:
        try: user = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt): break
        if not user: continue
        if user.lower() in ["sair", "exit"]: break
        if user.lower() == "squads":
            for k in SQUADS: print(f"  {k}"); continue
        if user.lower() == "agentes":
            agents = await factory_list()
            for a in agents: print(f"  {a['id']} [{a['status']}]"); continue
        force, msg = None, user
        if user.startswith("@"):
            parts = user.split(" ", 1)
            c     = parts[0][1:]
            if c in SQUADS: force, msg = c, (parts[1] if len(parts) > 1 else "olá")
        r = await process(msg, session_id, force)
        print(f"\n[{r['squad']} → {r['chief']}]\nELI: {r['response']}\n")

async def single(msg):
    return await process(msg, str(uuid.uuid4())[:8])

if __name__ == "__main__":
    if len(sys.argv) > 1:
        r = asyncio.run(single(" ".join(sys.argv[1:])))
        print(f"\n[{r['squad']} → {r['chief']}]\n{r['response']}")
    else:
        asyncio.run(chat())
# CIRCUIT BREAKER OPENROUTER
try:
    from openai import OpenAI as _OAI
except:
    _OAI=None
def _or_client():
    import os
    from openai import OpenAI
    return OpenAI(api_key=os.getenv("OPENROUTER_API_KEY"),base_url="https://openrouter.ai/api/v1")

