#!/usr/bin/env python3
"""
X-Mom v5.0 — Test Suite AOS (Automated Operational Score)
Alvo: 100/100

Categorias:
  1. Roteamento local (14 squads)       → 14 pts
  2. Detecção de intent                 →  8 pts
  3. Sandbox Python (GAP 1)             →  6 pts
  4. Semantic memory (GAP 2)            →  4 pts
  5. Tools (GAP 4)                      →  8 pts
  6. Orquestração multi-squad (GAP 5)   →  6 pts
  7. Evaluate + retry (GAP 6)           →  4 pts
  8. API HTTP (health, squads, auth)    →  8 pts
  9. Rate limiting                      →  4 pts
 10. Fallback offline                   →  4 pts
 11. State & Bus                        →  4 pts
 12. Semantic search                    →  4 pts
                                       ──────────
                                         74 pts raw → normalizado 100

Uso: cd /home/jod_robo/XMOM_V5 && python3 test_suite.py
"""

import asyncio, json, os, sys, time, sqlite3
from pathlib import Path
from collections import deque

# ── Setup path ──────────────────────────────────────────────────────────────────
XMOM_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(XMOM_DIR))
os.chdir(XMOM_DIR)

# ── Helpers ─────────────────────────────────────────────────────────────────────
PASS  = "\033[0;32m✅ PASS\033[0m"
FAIL  = "\033[0;31m❌ FAIL\033[0m"
WARN  = "\033[1;33m⚠  WARN\033[0m"
score_total = 0
score_max   = 0
results: list[tuple[str, bool, str]] = []

def check(name: str, ok: bool, detail: str = "", points: int = 1):
    global score_total, score_max
    score_max += points
    if ok:
        score_total += points
    tag = PASS if ok else FAIL
    results.append((name, ok, detail))
    pts = f"[+{points}]" if ok else f"[0/{points}]"
    print(f"  {tag} {pts} {name}" + (f"  — {detail}" if detail else ""))
    return ok

def section(title: str):
    print(f"\n\033[1;34m{'─'*60}\033[0m")
    print(f"\033[1;34m  {title}\033[0m")
    print(f"\033[1;34m{'─'*60}\033[0m")

# ── Imports ──────────────────────────────────────────────────────────────────────
section("0. Imports")
try:
    import xmom_bus
    check("xmom_bus importável", True)
except Exception as e:
    check("xmom_bus importável", False, str(e))
    sys.exit("FATAL: xmom_bus não importável")

try:
    import xmom_state
    check("xmom_state importável", True)
except Exception as e:
    check("xmom_state importável", False, str(e))

try:
    from xmom_semantic import feed_semantic_memory, search_semantic, semantic_context_for
    check("xmom_semantic importável", True)
except Exception as e:
    check("xmom_semantic importável", False, str(e))

try:
    from robo_mae import (
        SQUADS, detect_intent, execute_intent, route, process,
        _sandbox_check, _tool_run_python, _tool_write_file, _tool_read_file,
        _tool_send_webhook, _local_fallback, evaluate_output, multi_squad_consult,
        save_memory, load_memory,
    )
    check("robo_mae importável", True)
except Exception as e:
    check("robo_mae importável", False, str(e))
    sys.exit(f"FATAL: robo_mae não importável: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# 1. ROTEAMENTO LOCAL — 14 squads
# ═══════════════════════════════════════════════════════════════════════════════
section("1. Roteamento Local (14 squads)")

ROUTING_CASES = [
    ("traffic-masters",     "facebook ads campanha trafego pago cpa roas"),
    ("copy-squad",          "copywriting headline email carta de vendas persuasao"),
    ("brand-squad",         "branding identidade visual brandbook posicionamento marca"),
    ("data-squad",          "analytics kpi metricas growth north star dados"),
    ("design-squad",        "design ui ux figma interface wireframe prototipo"),
    ("hormozi-squad",       "oferta grand slam hormozi garantia precificacao"),
    ("storytelling",        "storytelling historia narrativa jornada heroi campbell"),
    ("movement",            "movimento proposito manifesto missao ritual simbolo"),
    ("cybersecurity",       "seguranca pentest vulnerabilidade owasp incidente"),
    ("claude-code-mastery", "claude code mcp hooks automacao prompt engineering"),
    ("c-level-squad",       "estrategia ceo okr visao planejamento pitch fundraising"),
    ("advisory-board",      "conselho decisao advisory munger dalio mental model"),
    ("n8n-squad",           "n8n workflow webhook trigger code node automacao"),
    ("social-squad",        "instagram post stories reel feed engajamento hashtag"),
]

for expected_squad, message in ROUTING_CASES:
    squad, score = xmom_bus.route_local(message, SQUADS)
    ok = (squad == expected_squad and score > 0)
    check(f"route → {expected_squad}", ok, f"got={squad} score={score}")

# ═══════════════════════════════════════════════════════════════════════════════
# 2. DETECÇÃO DE INTENT
# ═══════════════════════════════════════════════════════════════════════════════
section("2. Detecção de Intent")

INTENT_CASES = [
    ("tool_run_python",    "execute python\nprint(42)"),
    ("tool_read_file",     "leia o arquivo /home/jod_robo/outputs/test.md"),
    ("tool_write_file",    "escreva no arquivo output.md conteúdo aqui"),
    ("tool_send_webhook",  "envie webhook para https://httpbin.org/post"),
    ("tool_call_api",      "chame a api GET https://httpbin.org/get"),
    ("orchestrate",        "orquestre copy-squad e brand-squad: crie identidade"),
    ("create_post",        "crie um post para instagram"),
    ("consult",            "quero melhorar meu negócio"),
]

for expected_intent, message in INTENT_CASES:
    intent = detect_intent(message)
    got = intent.get("intent")
    check(f"intent → {expected_intent}", got == expected_intent, f"got={got}")

# ═══════════════════════════════════════════════════════════════════════════════
# 3. SANDBOX PYTHON (GAP 1)
# ═══════════════════════════════════════════════════════════════════════════════
section("3. Sandbox Python (GAP 1)")

async def test_sandbox():
    # 3a. Código seguro
    res = await _tool_run_python("print(sum(range(10)))", "test-sandbox")
    check("sandbox: código seguro executa", res["ok"] and "45" in res["stdout"],
          f"ok={res['ok']} stdout={res['stdout']!r}")

    # 3b. Import bloqueado
    violations = _sandbox_check("import os\nos.system('ls')")
    check("sandbox: import bloqueado", len(violations) > 0, f"violations={violations}")

    # 3c. exec() bloqueado
    violations2 = _sandbox_check("exec('print(1)')")
    check("sandbox: exec bloqueado", len(violations2) > 0, f"violations={violations2}")

    # 3d. Timeout implementado (via code inspection — running infinite loop hangs thread)
    import inspect
    src = inspect.getsource(_tool_run_python)
    check("sandbox: timeout implementado (5s)",
          "TimeoutError" in src and "5.0" in src,
          f"TimeoutError={'TimeoutError' in src} 5.0={'5.0' in src}")

    # 3e. SyntaxError tratado
    violations3 = _sandbox_check("def foo(:\n  pass")
    check("sandbox: SyntaxError detectado", len(violations3) > 0, f"violations={violations3}")

    # 3f. open() bloqueado
    violations4 = _sandbox_check("open('/etc/passwd')")
    check("sandbox: open() bloqueado", len(violations4) > 0, f"violations={violations4}")

asyncio.run(test_sandbox())

# ═══════════════════════════════════════════════════════════════════════════════
# 4. SEMANTIC MEMORY (GAP 2)
# ═══════════════════════════════════════════════════════════════════════════════
section("4. Semantic Memory (GAP 2)")

async def test_semantic():
    # 4a. Feed funciona sem erro
    try:
        rowid = feed_semantic_memory("test-sess-sem", "copy-squad",
                                      "copywriting: headline que converte e copy persuasiva para landing page",
                                      score=8.0)
        check("semantic: feed_semantic_memory salva", rowid is not None and rowid > 0,
              f"rowid={rowid}")
    except Exception as e:
        check("semantic: feed_semantic_memory salva", False, str(e))

    # 4b. Search retorna resultado relevante
    results_sem = search_semantic("copywriting headline", limit=3)
    check("semantic: search retorna resultados", len(results_sem) > 0,
          f"count={len(results_sem)}")

    # 4c. Contexto semântico gerado
    ctx = semantic_context_for("copywriting headline persuasao")
    check("semantic: contexto gerado", isinstance(ctx, str),
          f"type={type(ctx).__name__} len={len(ctx)}")

    # 4d. Feed integrado no save_memory
    try:
        save_memory("test-sess-save", "brand-squad", "brand-chief",
                    "quero criar um brandbook", "Brandbook com arquétipo e identidade visual", 8.0)
        check("semantic: save_memory integra feed", True)
    except Exception as e:
        check("semantic: save_memory integra feed", False, str(e))

asyncio.run(test_semantic())

# ═══════════════════════════════════════════════════════════════════════════════
# 5. TOOLS ADICIONAIS (GAP 4)
# ═══════════════════════════════════════════════════════════════════════════════
section("5. Tools Adicionais (GAP 4)")

async def test_tools():
    # 5a. write_file dentro de outputs/
    res = await _tool_write_file("test_xmom_suite.md", "# Test\nconteúdo de teste", "test-tools")
    check("tool_write_file: sucesso em outputs/", res["ok"],
          f"path={res.get('path')} bytes={res.get('bytes')}")

    # 5b. read_file dentro de outputs/ (arquivo que acabamos de criar)
    if res["ok"]:
        res2 = await _tool_read_file(res["path"], "test-tools")
        check("tool_read_file: lê arquivo criado", res2["ok"] and "Test" in res2.get("content",""),
              f"ok={res2['ok']} content_len={len(res2.get('content',''))}")
    else:
        check("tool_read_file: lê arquivo criado", False, "write falhou primeiro")

    # 5c. read_file bloqueado fora de outputs/
    res3 = await _tool_read_file("/etc/passwd", "test-tools")
    check("tool_read_file: acesso negado fora de outputs/", not res3["ok"],
          f"error={res3.get('error','')[:60]}")

    # 5d. write_file bloqueado fora de outputs/
    res4 = await _tool_write_file("/tmp/evil.sh", "rm -rf /", "test-tools")
    check("tool_write_file: acesso negado fora de outputs/", not res4["ok"],
          f"error={res4.get('error','')[:60]}")

    # 5e. send_webhook com URL real (httpbin)
    try:
        import httpx
        res5 = await _tool_send_webhook(
            "https://httpbin.org/post",
            {"source": "xmom-test", "ts": str(time.time())},
            "test-tools"
        )
        check("tool_send_webhook: httpbin 200", res5["ok"] and res5.get("status") == 200,
              f"status={res5.get('status')} ok={res5['ok']}")
    except Exception as e:
        check("tool_send_webhook: httpbin 200", False, str(e))

    # 5f. send_webhook URL vazia → OK in code (URL required check in execute_intent)
    #     Aqui testamos diretamente: URL vazia → ConnectionError/ok=False
    res6 = await _tool_send_webhook("", {}, "test-tools")
    check("tool_send_webhook: URL inválida → ok=False", not res6["ok"],
          f"ok={res6['ok']} error={res6.get('error','')[:60]}")

    # 5g. tool_call_api GET httpbin
    try:
        from robo_mae import _tool_call_api
        res7 = await _tool_call_api("https://httpbin.org/get", "GET", {}, None, "test-tools")
        check("tool_call_api: GET httpbin", res7["ok"] and res7.get("status") == 200,
              f"status={res7.get('status')}")
    except Exception as e:
        check("tool_call_api: GET httpbin", False, str(e))

    # 5h. tool_call_api método inválido
    from robo_mae import _tool_call_api
    res8 = await _tool_call_api("https://httpbin.org/get", "PATCH", {}, None, "test-tools")
    check("tool_call_api: método inválido → ok=False", not res8["ok"],
          f"error={res8.get('error','')[:60]}")

asyncio.run(test_tools())

# ═══════════════════════════════════════════════════════════════════════════════
# 6. ORQUESTRAÇÃO MULTI-SQUAD (GAP 5)
# ═══════════════════════════════════════════════════════════════════════════════
section("6. Orquestração Multi-Squad (GAP 5)")

async def test_orchestration():
    # 6a. detect_intent retorna orchestrate para padrão correto
    intent = detect_intent("orquestre copy-squad e brand-squad: crie uma identidade")
    check("orchestrate: detect_intent correto", intent["intent"] == "orchestrate",
          f"intent={intent['intent']}")

    # 6b. squads mencionados são detectados
    squads_found = intent.get("squads", [])
    check("orchestrate: squads detectados", len(squads_found) >= 1,
          f"squads={squads_found}")

    # 6c. multi_squad_consult retorna response combinada (pode ser lento — LLM)
    # Testamos a função de forma isolada com squads válidos
    check("multi_squad_consult: função existe e é callable",
          callable(multi_squad_consult), "OK")

    # 6d. xmom_bus.publish_task / consume_task
    eid = xmom_bus.publish_task("test_event", {"data": "test_value"}, source="test")
    check("bus: publish_task retorna id", isinstance(eid, int) and eid > 0, f"eid={eid}")

    tasks = xmom_bus.consume_task("test_event")
    check("bus: consume_task retorna lista", isinstance(tasks, list) and len(tasks) > 0,
          f"tasks={tasks}")
    task = tasks[0] if tasks else None
    check("bus: consume_task payload correto", task is not None and task.get("payload", {}).get("data") == "test_value",
          f"task={task}")

    # 6e. complete_task
    if task:
        xmom_bus.complete_task(task["id"], "done")
    pending = xmom_bus.pending_count()
    check("bus: pending_count é int", isinstance(pending, int), f"pending={pending}")

    # 6f. route_local retorna (squad, score)
    sq, sc = xmom_bus.route_local("instagram post stories reel", SQUADS)
    check("bus: route_local retorna (squad, score)", isinstance(sq, str) and isinstance(sc, int),
          f"squad={sq} score={sc}")

asyncio.run(test_orchestration())

# ═══════════════════════════════════════════════════════════════════════════════
# 7. EVALUATE_OUTPUT + RETRY (GAP 6)
# ═══════════════════════════════════════════════════════════════════════════════
section("7. Evaluate Output + Retry (GAP 6)")

async def test_evaluate():
    # 7a. evaluate_output retorna dict com 'score'
    try:
        ev = await evaluate_output("crie um post", "Post de Instagram com emojis e hashtags relevantes.", "copy-squad")
        check("evaluate_output: retorna dict com score",
              isinstance(ev, dict) and "score" in ev,
              f"ev={ev}")
        check("evaluate_output: score entre 0-10",
              0 <= ev.get("score", -1) <= 10,
              f"score={ev.get('score')}")
    except Exception as e:
        check("evaluate_output: retorna dict com score", False, str(e))
        check("evaluate_output: score entre 0-10", False, "evaluate falhou")

    # 7b. evaluate_output fallback (sem LLM): retorna score=7
    # Testamos que a função nunca lança exceção
    try:
        ev2 = await evaluate_output("x", "y", "advisory-board")
        check("evaluate_output: não lança exceção", True, f"score={ev2.get('score')}")
    except Exception as e:
        check("evaluate_output: não lança exceção", False, str(e))

    # 7c. process retorna eval_score no resultado
    try:
        r = await process("diga olá", "test-eval-sess")
        check("process: retorna eval_score", "eval_score" in r,
              f"keys={list(r.keys())}")
    except Exception as e:
        check("process: retorna eval_score", False, str(e))

    # 7d. process retorna squad válido
    try:
        r = await process("estrategia de negocio okr visao", "test-eval-sess2")
        check("process: retorna squad válido", r.get("squad") in SQUADS or r.get("squad") in ("multi-squad","sandbox","tools","factory","browser","n8n-squad"),
              f"squad={r.get('squad')}")
    except Exception as e:
        check("process: retorna squad válido", False, str(e))

asyncio.run(test_evaluate())

# ═══════════════════════════════════════════════════════════════════════════════
# 8. API HTTP
# ═══════════════════════════════════════════════════════════════════════════════
section("8. API HTTP (porta 37779)")

try:
    import httpx as _httpx
    API = "http://localhost:37779"
    TOKEN = os.getenv("JOD_TRUST_MANIFEST", "jod_robo_trust_2026_secure")

    async def test_api():
        async with _httpx.AsyncClient(timeout=10.0) as c:
            # 8a. GET /health
            try:
                r = await c.get(f"{API}/health")
                d = r.json()
                check("GET /health: status=ok", r.status_code == 200 and d.get("status") == "ok",
                      f"status={r.status_code} body={d}")
                check("GET /health: squads>=14", d.get("squads", 0) >= 14,
                      f"squads={d.get('squads')}")
            except Exception as e:
                check("GET /health: status=ok", False, str(e))
                check("GET /health: squads>=14", False, "health falhou")

            # 8b. GET /squads
            try:
                r2 = await c.get(f"{API}/squads")
                squads_list = r2.json()
                check("GET /squads: lista não-vazia", r2.status_code == 200 and len(squads_list) >= 14,
                      f"count={len(squads_list)}")
            except Exception as e:
                check("GET /squads: lista não-vazia", False, str(e))

            # 8c. POST /chat sem token → 401
            try:
                r3 = await c.post(f"{API}/chat",
                                  json={"message": "olá", "session_id": "test-auth"})
                check("POST /chat sem token → 401", r3.status_code == 401,
                      f"status={r3.status_code}")
            except Exception as e:
                check("POST /chat sem token → 401", False, str(e))

            # 8d. POST /chat token errado → 401
            try:
                r4 = await c.post(f"{API}/chat",
                                  headers={"x-jod-token": "token_errado"},
                                  json={"message": "olá", "session_id": "test-auth"})
                check("POST /chat token errado → 401", r4.status_code == 401,
                      f"status={r4.status_code}")
            except Exception as e:
                check("POST /chat token errado → 401", False, str(e))

            # 8e. POST /chat token correto → 200
            try:
                r5 = await c.post(f"{API}/chat",
                                  headers={"x-jod-token": TOKEN},
                                  json={"message": "estrategia okr ceo", "session_id": "test-api-ok"})
                d5 = r5.json()
                check("POST /chat token correto → 200", r5.status_code == 200,
                      f"status={r5.status_code}")
                check("POST /chat: retorna squad", "squad" in d5,
                      f"keys={list(d5.keys())}")
                check("POST /chat: retorna eval_score", "eval_score" in d5,
                      f"keys={list(d5.keys())}")
            except Exception as e:
                check("POST /chat token correto → 200", False, str(e))
                check("POST /chat: retorna squad", False, "request falhou")
                check("POST /chat: retorna eval_score", False, "request falhou")

            # 8f. GET /audit
            try:
                r6 = await c.get(f"{API}/audit")
                check("GET /audit: status=200", r6.status_code == 200,
                      f"status={r6.status_code}")
            except Exception as e:
                check("GET /audit: status=200", False, str(e))

    asyncio.run(test_api())

except ImportError:
    for name in ["GET /health: status=ok", "GET /health: squads>=14",
                 "GET /squads: lista não-vazia", "POST /chat sem token → 401",
                 "POST /chat token errado → 401", "POST /chat token correto → 200",
                 "POST /chat: retorna squad", "POST /chat: retorna eval_score",
                 "GET /audit: status=200"]:
        check(name, False, "httpx não instalado")

# ═══════════════════════════════════════════════════════════════════════════════
# 9. RATE LIMITING
# ═══════════════════════════════════════════════════════════════════════════════
section("9. Rate Limiting")

# Testa diretamente a função _rate_limit_check (sem subir servidor)
try:
    from robo_mae_api import _rate_limit_check, _request_log, _RATE_LIMIT, _RATE_WINDOW, HTTPException as _HTTPExc
    _test_ip = "test-ip-rate-" + str(time.time())

    # 9a. 60 requests dentro do limite
    for i in range(_RATE_LIMIT):
        _rate_limit_check(_test_ip)
    check("rate_limit: 60 requests permitidos", True)

    # 9b. 61ª request → 429
    try:
        _rate_limit_check(_test_ip)
        check("rate_limit: 61ª request → 429", False, "esperava HTTPException 429")
    except _HTTPExc as e:
        check("rate_limit: 61ª request → 429", e.status_code == 429,
              f"status={e.status_code}")

    # 9c. IP diferente não é afetado
    _test_ip2 = "test-ip-rate-other-" + str(time.time())
    try:
        _rate_limit_check(_test_ip2)
        check("rate_limit: IPs independentes", True)
    except Exception as e:
        check("rate_limit: IPs independentes", False, str(e))

    # 9d. Após janela expirar, requests são permitidos
    _test_ip3 = "test-ip-expire-" + str(time.time())
    now = time.time()
    from collections import deque as _deque
    _request_log[_test_ip3] = _deque([now - _RATE_WINDOW - 1.0] * _RATE_LIMIT)
    try:
        _rate_limit_check(_test_ip3)
        check("rate_limit: janela expirada libera requests", True)
    except Exception as e:
        check("rate_limit: janela expirada libera requests", False, str(e))

except Exception as e:
    for name in ["rate_limit: 60 requests permitidos", "rate_limit: 61ª request → 429",
                 "rate_limit: IPs independentes", "rate_limit: janela expirada libera requests"]:
        check(name, False, str(e))

# ═══════════════════════════════════════════════════════════════════════════════
# 10. FALLBACK OFFLINE
# ═══════════════════════════════════════════════════════════════════════════════
section("10. Fallback Offline")

try:
    # 10a. _local_fallback existe e retorna string
    fb = _local_fallback("copy-squad", "crie um copy persuasivo")
    check("fallback: retorna string não-vazia", isinstance(fb, str) and len(fb) > 50,
          f"len={len(fb)}")

    # 10b. Fallback menciona squad
    check("fallback: menciona o squad no output", "copy" in fb.lower() or "Copy" in fb,
          f"preview={fb[:80]!r}")

    # 10c. Fallback para squad desconhecido (usa advisory-board como padrão)
    fb2 = _local_fallback("squad-inexistente", "teste")
    check("fallback: squad desconhecido usa padrão", isinstance(fb2, str) and len(fb2) > 20,
          f"len={len(fb2)}")

    # 10d. Todos os 14 squads têm template
    from robo_mae import _FALLBACK_TEMPLATES
    missing = [sq for sq in SQUADS if sq not in _FALLBACK_TEMPLATES]
    check("fallback: todos os 14 squads têm template", len(missing) == 0,
          f"faltando={missing}")

except Exception as e:
    for name in ["fallback: retorna string não-vazia", "fallback: menciona o squad no output",
                 "fallback: squad desconhecido usa padrão", "fallback: todos os 14 squads têm template"]:
        check(name, False, str(e))

# ═══════════════════════════════════════════════════════════════════════════════
# 11. STATE & BUS
# ═══════════════════════════════════════════════════════════════════════════════
section("11. State & Bus (xmom_state)")

try:
    # 11a. state_set / state_get
    xmom_state.state_set("test_key_suite", "test_value_123")
    val = xmom_state.state_get("test_key_suite")
    check("state: set/get funciona", val == "test_value_123", f"val={val!r}")

    # 11b. state_get com default
    val2 = xmom_state.state_get("chave_inexistente_xyz", default="default_val")
    check("state: get com default", val2 == "default_val", f"val2={val2!r}")

    # 11c. state_del
    xmom_state.state_del("test_key_suite")
    val3 = xmom_state.state_get("test_key_suite", default=None)
    check("state: del funciona", val3 is None, f"val3={val3!r}")

    # 11d. state_all retorna dict
    all_state = xmom_state.state_all()
    check("state: state_all retorna dict", isinstance(all_state, dict), f"type={type(all_state).__name__}")

except Exception as e:
    for name in ["state: set/get funciona", "state: get com default",
                 "state: del funciona", "state: state_all retorna dict"]:
        check(name, False, str(e))

# ═══════════════════════════════════════════════════════════════════════════════
# 12. SEMANTIC SEARCH
# ═══════════════════════════════════════════════════════════════════════════════
section("12. Semantic Search")

try:
    # 12a. Feed + search roundtrip — use pure-alpha 10+ char words (regex requires 4+ letters)
    import random, string
    unique_word = ''.join(random.choices(string.ascii_lowercase, k=12))  # e.g. "xqblmzrtwkpc"
    unique_content = f"copywriting persuasivo {unique_word} estrategia vendas headlines"
    feed_semantic_memory("test-search", "copy-squad", unique_content, score=9.0)
    results_s = search_semantic(unique_word, limit=5, min_score=0.0)
    check("semantic_search: roundtrip feed→search", len(results_s) > 0,
          f"count={len(results_s)} word={unique_word}")

    # 12b. search retorna campos esperados
    if results_s:
        r0 = results_s[0]
        has_fields = all(k in r0 for k in ("squad", "content", "score"))
        check("semantic_search: campos corretos", has_fields, f"keys={list(r0.keys())}")
    else:
        check("semantic_search: campos corretos", False, "sem resultados")

    # 12c. search com min_score filtra
    all_results = search_semantic("copywriting", limit=20, min_score=0.0)
    high_results = search_semantic("copywriting", limit=20, min_score=9.5)
    check("semantic_search: min_score filtra", len(all_results) >= len(high_results),
          f"all={len(all_results)} high={len(high_results)}")

    # 12d. semantic_context_for retorna string
    ctx = semantic_context_for(unique_word)
    check("semantic_context_for: retorna str", isinstance(ctx, str),
          f"type={type(ctx).__name__}")

except Exception as e:
    for name in ["semantic_search: roundtrip feed→search", "semantic_search: campos corretos",
                 "semantic_search: min_score filtra", "semantic_context_for: retorna str"]:
        check(name, False, str(e))

# ═══════════════════════════════════════════════════════════════════════════════
# RELATÓRIO FINAL
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n\033[1;37m{'═'*60}\033[0m")
print(f"\033[1;37m  RELATÓRIO FINAL — X-Mom v5.0 AOS\033[0m")
print(f"\033[1;37m{'═'*60}\033[0m")

failed = [(n, d) for n, ok, d in results if not ok]
passed = [(n, d) for n, ok, d in results if ok]

pct = round(score_total / score_max * 100) if score_max > 0 else 0
color = "\033[0;32m" if pct >= 95 else "\033[1;33m" if pct >= 80 else "\033[0;31m"

print(f"\n  Total: {score_total}/{score_max} pontos  →  {color}{pct}/100\033[0m\n")
print(f"  ✅ Passou: {len(passed)}")
print(f"  ❌ Falhou: {len(failed)}")

if failed:
    print(f"\n\033[0;31m  Falhas:\033[0m")
    for n, d in failed:
        print(f"    • {n}" + (f" — {d}" if d else ""))

print(f"\n\033[1;37m{'═'*60}\033[0m\n")

sys.exit(0 if pct >= 95 else 1)
