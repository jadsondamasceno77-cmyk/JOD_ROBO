#!/usr/bin/env python3
"""
JOD_ROBO — Robô-mãe v4.0
CAMADA 1: Factory (cria/ativa/executa agentes reais)
CAMADA 2: Consultores LLM (152 especialistas via Groq)
EXECUÇÃO REAL: agente_browser navega/screenshot, especialistas geram arquivos .md
24/7: roda como serviço via systemd
"""

import asyncio, json, os, sqlite3, uuid, httpx, sys
from datetime import datetime, timezone
from pathlib import Path
from groq import Groq
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def _llm_call(messages, temperature=0.7, max_tokens=1024):
    """Circuit breaker: Groq -> OpenRouter x3 -> fallback."""
    try:
        r=client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,temperature=temperature,max_tokens=max_tokens)
        return r.choices[0].message.content.strip()
    except Exception as e:
        if "429" not in str(e) and "rate_limit" not in str(e).lower():
            raise
    import httpx as _hx, time as _t
    or_key=os.getenv("OPENROUTER_API_KEY","")
    if or_key:
        for attempt in range(3):
            try:
                r=_hx.post("https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization":f"Bearer {or_key}","Content-Type":"application/json"},
                    json={"model":"meta-llama/llama-3.3-70b-instruct","messages":messages,"temperature":temperature,"max_tokens":max_tokens},
                    timeout=30.0)
                if r.status_code == 200:
                    return r.json()["choices"][0]["message"]["content"].strip()
            except Exception as e2:
                _t.sleep(2)
    try:
        r=client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,temperature=temperature,max_tokens=max_tokens)
        return r.choices[0].message.content.strip()
    except Exception:
        pass
    return "ELI processando. Tente novamente."

DB_PATH = Path(__file__).resolve().parent / "jod_robo.db"
MEMORY_PATH = Path(__file__).resolve().parent / "memory"
OUTPUT_PATH = Path(__file__).resolve().parent / "outputs"
MEMORY_PATH.mkdir(exist_ok=True)
OUTPUT_PATH.mkdir(exist_ok=True)

# ─── FACTORY ────────────────────────────────────────────────────────────────────
FACTORY_URL = "http://localhost:37777"
TRUST_TOKEN = os.getenv("JOD_TRUST_MANIFEST", "jod_robo_trust_2026_secure")
FACTORY_AGENTS = ["agente_finalizador","agente_guardiao","agente_planner",
                  "agente_suporte_01","agente_browser","agente_memoria","agente_dados"]
FACTORY_TEMPLATES = ["support","executor","scheduler","analyzer","crawler"]

SQUADS = {
    "traffic-masters": {"chief":"traffic-chief","keywords":["trafego","traffic","anuncio","ads","facebook ads","google ads","meta","campanha","cpa","roas","midia paga"]},
    "copy-squad":      {"chief":"copy-chief","keywords":["copy","copywriting","texto","headline","email","carta de vendas","persuasao","script","roteiro","vsl","landing page"]},
    "brand-squad":     {"chief":"brand-chief","keywords":["marca","brand","branding","posicionamento","identidade","logo","naming","arquetipo","brandbook","brand book","guia de marca","manual de marca","identidade visual","tom de voz"]},
    "data-squad":      {"chief":"data-chief","keywords":["dados","analytics","metricas","kpi","growth","retencao","churn","clv","ltv","cohort","north star","pmf"]},
    "design-squad":    {"chief":"design-chief","keywords":["design","ui","ux","interface","figma","prototipo","wireframe","design system"]},
    "hormozi-squad":   {"chief":"hormozi-chief","keywords":["oferta","offer","precificacao","preco","hormozi","grand slam","value stack","garantia","bonus"]},
    "storytelling":    {"chief":"story-chief","keywords":["historia","story","narrativa","storytelling","jornada","heroi","arco","campbell"]},
    "movement":        {"chief":"movement-chief","keywords":["movimento","proposito","missao","manifesto","ritual","simbolo"]},
    "cybersecurity":   {"chief":"cyber-chief","keywords":["seguranca","security","pentest","vulnerabilidade","hacking","owasp","incidente"]},
    "claude-code-mastery":{"chief":"claude-mastery-chief","keywords":["claude code","mcp","hooks","automacao","prompt engineering"]},
    "c-level-squad":   {"chief":"vision-chief","keywords":["estrategia","ceo","coo","cto","cmo","visao","okr","planejamento","fundraising","pitch"]},
    "advisory-board":  {"chief":"board-chair","keywords":["conselho","advisory","decisao","mental model","dalio","munger","thiel","naval","principios"]},
    "n8n-squad":       {"chief":"n8n-chief","keywords":["n8n","workflow","automacao","webhook","node","integracao","http request","schedule","trigger","code node","langchain","ai node","subworkflow","error handling","docker n8n","postgres n8n","redis n8n","queue mode","oauth","api integration","automatizar","criar workflow","novo workflow"]},
}

# ─── FACTORY CALLS ──────────────────────────────────────────────────────────────

async def factory_call(method, path, payload=None):
    headers = {
        "Content-Type":"application/json",
        "x-trust-token": TRUST_TOKEN,
        "x-request-id": f"rm-{str(uuid.uuid4())[:8]}",
        "x-idempotency-key": str(uuid.uuid4())
    }
    async with httpx.AsyncClient(timeout=15.0) as http:
        if method == "POST":
            r = await http.post(f"{FACTORY_URL}{path}", headers=headers, json=payload)
        else:
            r = await http.get(f"{FACTORY_URL}{path}", headers=headers)
    return r.json()

async def factory_wait(task_id, tries=20):
    for i in range(tries):
        await asyncio.sleep(0.5 + i*0.1)
        try:
            r = await factory_call("GET", f"/tasks/{task_id}")
            if r.get("status") in ("succeeded","failed","rolled_back"):
                return r
        except: pass
    return {"status":"timeout"}

async def factory_list():
    try: return await factory_call("GET", "/agents")
    except: return []

async def factory_create(template, agent_id, name):
    r = await factory_call("POST", "/agents/create-from-template", {
        "action_type":"create_agent_from_template",
        "parameters":{"template_name":template,"new_agent_id":agent_id,"name":name}
    })
    return await factory_wait(r.get("task_id")) if r.get("task_id") else r

async def factory_activate(agent_id):
    r = await factory_call("POST", "/agents/activate", {
        "action_type":"activate_agent","parameters":{"agent_id":agent_id}
    })
    return await factory_wait(r.get("task_id")) if r.get("task_id") else r

async def factory_validate(agent_id):
    r = await factory_call("POST", "/agents/validate", {
        "action_type":"validate_agent","parameters":{"agent_id":agent_id}
    })
    return await factory_wait(r.get("task_id")) if r.get("task_id") else r

# ─── EXECUÇÃO REAL: BROWSER ─────────────────────────────────────────────────────

async def browser_navigate(url: str) -> dict:
    """Chama agente_browser real via Playwright."""
    try:
        import importlib.util, sys
        browser_path = Path(__file__).resolve().parent / "agents" / "agente_browser" / "main.py"
        spec = importlib.util.spec_from_file_location("agente_browser", browser_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        result = await mod.navigate(url)
        return result
    except Exception as e:
        return {"error": str(e), "url": url}

async def browser_screenshot(url: str) -> dict:
    """Tira screenshot via agente_browser."""
    try:
        import importlib.util
        browser_path = Path(__file__).resolve().parent / "agents" / "agente_browser" / "main.py"
        spec = importlib.util.spec_from_file_location("agente_browser", browser_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        result = await mod.screenshot(url)
        return result
    except Exception as e:
        return {"error": str(e)}

# ─── EXECUÇÃO REAL: GERAR ARQUIVO ───────────────────────────────────────────────

def save_output(filename: str, content: str) -> str:
    """Salva conteúdo em arquivo na pasta outputs/."""
    path = OUTPUT_PATH / filename
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return str(path)

# ─── DETECTOR DE INTENÇÃO ───────────────────────────────────────────────────────

def detect_intent(message: str) -> dict:
    import re
    ml = message.lower().strip()

    # BROWSER — screenshot
    shot_patterns = ["screenshot","print da tela","captura de tela","tire um print","foto do site","printscreen","print screen"]
    if any(p in ml for p in shot_patterns):
        url_m = re.search(r'https?://\S+|www\.\S+', message)
        return {"intent":"browser_screenshot","url": url_m.group(0) if url_m else "https://example.com"}

    # BROWSER — navegar
    url_m = re.search(r'https?://\S+|www\.\S+', message)
    nav_patterns = ["abra","abrir","acesse","acessar","navegue","navegar","vai para","vá para","abra o site","abra a url","visite","visita","abre o","pesquise","pesquisar","busque","buscar na web","procure na web"]
    if any(p in ml for p in nav_patterns) and url_m:
        return {"intent":"browser_navigate","url": url_m.group(0)}
    if any(p in ml for p in ["abra o site","abra a url","acesse o site","visite o site"]):
        return {"intent":"browser_navigate","url": url_m.group(0) if url_m else "https://example.com"}

    # FACTORY — listar
    if any(p in ml for p in ["liste os agentes","listar agentes","quais agentes","agentes ativos","ver agentes","mostre os agentes"]):
        return {"intent":"factory_list"}

    # FACTORY — ativar agente
    m = re.search(r'(ativ[ae]|start|inicie)\s+(o\s+)?agente[_\s]?(\w+)', ml, re.I)
    if m:
        return {"intent":"factory_activate","agent_id": m.group(3)}

    # FACTORY — validar agente
    m = re.search(r'(valid[ae]|test[ae]|chequ[ae])\s+(o\s+)?agente[_\s]?(\w+)', ml, re.I)
    if m:
        return {"intent":"factory_validate","agent_id": m.group(3)}

    # FACTORY — criar agente
    m = re.search(r'(cri[ae]|build|make|faz[er]*)\s+.*(agente|agent)\s*(\w+)?', ml, re.I)
    if m:
        aid = m.group(3) or "custom"
        return {"intent":"factory_create","template":"custom","agent_id":aid,"name":aid}

    # N8N — criar workflow (padrão amplo com LLM fallback)
    n8n_kw = ["workflow","automac","integrac","pipeline","fluxo n8n","webhook","schedule","agendamento","notificac","disparo automát","cron","trigger","n8n"]
    action_kw = ["cri","build","make","faz","constru","monta","desenvolv","implement","automat","configur","quero um","preciso de um","gera","gerar"]
    has_n8n = any(k in ml for k in n8n_kw)
    has_action = any(k in ml for k in action_kw)
    if has_n8n and has_action:
        return {"intent":"n8n_create","description":message}

    # N8N — listar
    if any(p in ml for p in ["liste os workflows","listar workflows","workflows existentes","meus workflows","ver workflows","quais workflows","mostre os workflows","show workflows"]):
        return {"intent":"n8n_list"}

    # N8N — ativar
    m = re.search(r'(ativ[ae]|enable|ligu[ae])\s+(o\s+)?workflow[_\s]?(\w+)?', ml, re.I)
    if m:
        return {"intent":"n8n_activate","workflow_id": m.group(3)}

    # SALVAR
    if any(p in ml for p in ["salve","salvar","gere um arquivo","criar arquivo","exportar","save this","baixar","download o resultado"]):
        return {"intent":"save_file"}

    # CRIAR PERFIS NAS REDES
    perfil_kw = ["perfil","perfis","redes sociais","criar conta","bio para","username para","presenca digital","identidade nas redes"]
    perfil_action = ["cri","monta","gera","faz","configur","estrutur"]
    if any(k in ml for k in perfil_kw) and any(a in ml for a in perfil_action):
        return {"intent":"criar_perfis","description":message}

    return {"intent":"consult"}


async def execute_intent(intent: dict, message: str, session_id: str) -> dict:
    i = intent["intent"]

    if i == "factory_list":
        agents = await factory_list()
        lines = [f"  - {a['id']} [{a['status']}]" for a in agents] if agents else ["  Factory indisponível"]
        return {"squad":"factory","chief":"factory","response":"Agentes no Factory:\n" + "\n".join(lines)}

    elif i == "factory_activate":
        aid = intent.get("agent_id")
        if not aid:
            return {"squad":"factory","chief":"factory","response":"Qual agente quer ativar? Ex: agente_browser"}
        r = await factory_activate(aid)
        return {"squad":"factory","chief":"factory","response":f"Agente `{aid}` → ativação: **{r.get('status','?')}**"}

    elif i == "factory_validate":
        aid = intent.get("agent_id")
        if not aid:
            return {"squad":"factory","chief":"factory","response":"Qual agente quer validar?"}
        r = await factory_validate(aid)
        return {"squad":"factory","chief":"factory","response":f"Agente `{aid}` → validação: **{r.get('status','?')}**"}

    elif i == "factory_create":
        r = await factory_create(intent["template"], intent["agent_id"], intent["name"])
        return {"squad":"factory","chief":"factory","response":f"Agente `{intent['agent_id']}` (template: {intent['template']}) → **{r.get('status','?')}**"}

    elif i == "browser_navigate":
        url = intent.get("url","https://example.com")
        result = await browser_navigate(url)
        if "error" in result:
            return {"squad":"browser","chief":"agente_browser","response":f"Erro ao navegar: {result['error']}"}
        resp = f"**Navegação concluída**\nURL: {result.get('url')}\nTítulo: {result.get('title')}\n\nConteúdo (500 chars):\n{result.get('content','')}"
        return {"squad":"browser","chief":"agente_browser","response":resp}

    elif i == "browser_screenshot":
        url = intent.get("url","https://example.com")
        result = await browser_screenshot(url)
        if "error" in result:
            return {"squad":"browser","chief":"agente_browser","response":f"Erro no screenshot: {result['error']}"}
        return {"squad":"browser","chief":"agente_browser","response":f"Screenshot salvo em: `{result.get('screenshot')}`"}

    elif i == "n8n_create":
        try:
            import importlib.util
            n8n_path = Path(__file__).resolve().parent / "agents" / "agente_n8n" / "main.py"
            if not n8n_path.exists():
                # Usa o agente_n8n.py direto na pasta JOD_ROBO se não estiver em agents/
                n8n_path = Path(__file__).resolve().parent / "agente_n8n.py"
            spec = importlib.util.spec_from_file_location("agente_n8n", n8n_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            result = await mod.create_from_description(intent.get("description","workflow"))
            return {"squad":"n8n-squad","chief":"n8n-chief",
                    "response":f"✅ Workflow criado no n8n!\n\n**Nome:** {result['name']}\n**ID:** {result['id']}\n**URL:** {result['url']}\n\nAcesse em: http://localhost:5678"}
        except Exception as e:
            return {"squad":"n8n-squad","chief":"n8n-chief","response":f"Erro ao criar workflow: {e}"}

    elif i == "n8n_list":
        try:
            import importlib.util
            n8n_path = Path(__file__).resolve().parent / "agente_n8n.py"
            spec = importlib.util.spec_from_file_location("agente_n8n", n8n_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            workflows = await mod.list_workflows()
            if not workflows:
                return {"squad":"n8n-squad","chief":"n8n-chief","response":"Nenhum workflow encontrado no n8n."}
            lines = [f"  - [{w['id']}] {w['name']} (ativo: {w['active']})" for w in workflows]
            return {"squad":"n8n-squad","chief":"n8n-chief","response":"Workflows no n8n:\n" + "\n".join(lines)}
        except Exception as e:
            return {"squad":"n8n-squad","chief":"n8n-chief","response":f"Erro ao listar workflows: {e}"}

    elif i == "n8n_activate":
        return {"squad":"n8n-squad","chief":"n8n-chief","response":"Qual o ID do workflow para ativar? Veja em 'liste os workflows'."}

    elif i == "save_file":
        # Consulta o especialista e salva o resultado em arquivo
        mem = load_memory(session_id)
        squad_name, score = route(message)
        if score == 0:
            squad_name = await route_llm(message)
        content = await consult(squad_name, message, mem)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{squad_name}_{ts}.md"
        path = save_output(filename, content)
        save_memory(session_id, squad_name, SQUADS[squad_name]["chief"], message, content)
        return {"squad":squad_name,"chief":SQUADS[squad_name]["chief"],
                "response":f"Arquivo salvo em:\n`{path}`\n\n---\n{content}"}

    elif i == "criar_perfis":
        import re
        desc = intent.get("description","")
        # Extrai marca, nicho, site, email da mensagem
        m_marca = re.search(r'(?:para|de|da|do|:)\s+([A-Za-zÀ-ú][A-Za-zÀ-ú\s]{1,40}?)(?=\s+nicho|\s+site|\s+email|\s+no\s|\s+em\s|\s+nas\s|$)', desc, re.I)
        m_nicho = re.search(r'nicho\s+([A-Za-zÀ-ú\s]{2,30}?)(?=\s+site|\s+email|$)', desc, re.I)
        m_site  = re.search(r'site\s+(\S+)', desc, re.I)
        m_email = re.search(r'email\s+(\S+)', desc, re.I)
        marca_nome = m_marca.group(1).strip() if m_marca else "Sua Marca"
        nicho_nome = m_nicho.group(1).strip() if m_nicho else "Negocio Digital"
        site_url   = m_site.group(1).strip() if m_site else ""
        email_val  = m_email.group(1).strip() if m_email else ""
        resultado = criar_perfis_redes(marca_nome, nicho_nome, site=site_url, email=email_val)
        save_memory(session_id, "brand-squad", "brand-chief", message, resultado)
        return {"squad":"brand-squad","chief":"brand-chief","response":resultado}
    # Fallback: consulta LLM
    return None

# ─── BANCO ──────────────────────────────────────────────────────────────────────

def get_agent_data(name):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT name,squad,role,tier,description,capabilities,persona FROM agents WHERE name=?", (name,))
    row = cur.fetchone()
    conn.close()
    if not row: return {}
    return {"name":row[0],"squad":row[1],"role":row[2],"tier":row[3],"description":row[4],"capabilities":row[5],"persona":row[6]}

def get_specialists(squad_name):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT name,description FROM agents WHERE squad=? AND tier>0 ORDER BY tier,name",(squad_name,))
    rows = cur.fetchall()
    conn.close()
    return rows

def save_memory(session_id, squad, agent, user_msg, response):
    with open(MEMORY_PATH/"conversations.jsonl","a") as f:
        f.write(json.dumps({"session_id":session_id,"timestamp":datetime.now(timezone.utc).isoformat(),
                            "squad":squad,"agent":agent,"user":user_msg,"response":response},ensure_ascii=False)+"\n")

def load_memory(session_id, limit=4):
    mf = MEMORY_PATH/"conversations.jsonl"
    if not mf.exists(): return []
    entries = []
    for line in open(mf):
        try:
            e = json.loads(line)
            if e.get("session_id")==session_id: entries.append(e)
        except: pass
    return entries[-limit:]

# ─── ROTEAMENTO ─────────────────────────────────────────────────────────────────

def route(message):
    ml = message.lower()
    scores = {sq: sum(1 for kw in data["keywords"] if kw in ml) for sq, data in SQUADS.items()}
    scores = {k:v for k,v in scores.items() if v > 0}
    if not scores: return "advisory-board", 0
    best = max(scores, key=scores.get)
    return best, scores[best]

async def route_llm(message):
    """Classifica mensagem no squad correto via LLM. Fallback: c-level-squad para perguntas gerais."""
    kw_hint = "\n".join([
        f"- {k}: {', '.join(data['keywords'][:4])}"
        for k, data in SQUADS.items()
    ])
    r = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role":"system","content":(
                "Voce e um classificador de intencoes. "
                "Dado uma mensagem, retorne APENAS o slug exato do squad mais adequado.\n"
                "Slugs validos e suas palavras-chave:\n" + kw_hint + "\n"
                "REGRA: mensagens curtas, pings, testes, saudacoes → c-level-squad.\n"
                "Retorne SOMENTE o slug, sem explicacao, sem markdown."
            )},
            {"role":"user","content":message}
        ],
        temperature=0.0, max_tokens=24
    )
    sq = r.choices[0].message.content.strip().lower().strip("`").strip()
    # Valida slug exato
    if sq in SQUADS:
        return sq
    # Tenta match parcial
    for slug in SQUADS:
        if slug in sq or sq in slug:
            return slug
    # Fallback inteligente por tamanho
    return "c-level-squad" if len(message.split()) <= 3 else "advisory-board"

# ─── CONSULTA LLM ────────────────────────────────────────────────────────────────

async def consult(squad_name, message, session_memory):
    chief_name = SQUADS[squad_name]["chief"]
    chief = get_agent_data(chief_name)
    specialists = get_specialists(squad_name)
    spec_list = "\n".join([f"- {n}: {d}" for n,d in specialists]) if specialists else "nenhum"

    brandbook = ""
    if squad_name == "brand-squad":
        brandbook = """
BRANDBOOK — fluxo em 6 fases:
1. archetype-consultant → arquetipo e personalidade
2. jean-noel-kapferer → Identity Prism (6 facetas)
3. al-ries → posicionamento e tagline
4. alina-wheeler → identidade visual completa
5. donald-miller → BrandScript e messaging
6. naming-strategist + domain-scout → nome e dominio
Diga ao usuario: para SALVAR o brandbook como arquivo, diga 'salve o brandbook'."""

    n8n_expert = ""
    if squad_name == "n8n-squad":
        n8n_expert = """
VOCE E UM N8N EXPERT FAIXA PRETA. Dominio completo de:

1. JAVASCRIPT E EXPRESSOES: Code Node, .map() .filter() .reduce(), manipulacao de JSON/Binary, expressoes $json/$node/$workflow
2. ARQUITETURA ESCALAVEL: Sub-workflows (Execute Workflow node), Error Handling (Error Trigger), Idempotencia, Split in Batches, Merge node
3. HTTP E WEBHOOKS: HTTP Request Node (GET/POST/PATCH/DELETE), OAuth2, Header Auth, API Key, Webhook Trigger, Respond to Webhook
4. INFRAESTRUTURA: Docker, Docker Compose, Postgres (producao), Redis + Queue Mode (execucoes paralelas), Self-hosting, .env config
5. IA E LANGCHAIN: AI Agent node, Chat Memory, RAG com Pinecone/Supabase, Embeddings, Vector Store, Tool nodes, LLM nodes (OpenAI/Groq/Anthropic)
6. VISAO DE NEGOCIO: Mapeamento de processos, ROI de automacao, identificacao de gargalos, arquitetura antes de abrir o n8n

CAPACIDADES DE EXECUCAO:
- "crie um workflow [descricao]" → cria o workflow real no n8n via API
- "liste os workflows" → lista workflows existentes
- "ative o workflow [id]" → ativa um workflow

TEMPLATES DISPONIVEIS:
- webhook + email
- schedule + HTTP request
- webhook + Code Node (JavaScript)
- AI Agent com LangChain
- Error Handler com notificacao

Ao responder perguntas de arquitetura, mostre o JSON do node quando relevante.
Ao sugerir criar algo, diga: 'Para criar agora, diga: crie um workflow [descricao]'"""

    system = f"""Voce e {chief.get('name','chief').replace('-',' ').title()}.
{chief.get('persona','')}
{chief.get('description','')}

ESPECIALISTAS REAIS (use APENAS estes nomes, NUNCA invente):
{spec_list}{brandbook}{n8n_expert}

CAPACIDADES DE EXECUCAO DISPONIVEIS:
- "abra o site [url]" → agente_browser navega e retorna conteudo
- "screenshot de [url]" → agente_browser tira print
- "salve [o resultado]" → gera arquivo .md em outputs/
- "liste os agentes" → Factory lista agentes ativos
- "crie um agente [tipo]" → Factory cria novo agente

REGRAS: Cite apenas nomes da lista. Responda em portugues. Seja direto e acionavel."""

    user_ctx = f"""{message}

[INTERNO]: Especialistas reais: {spec_list}"""

    msgs = [{"role":"system","content":system}]
    for mem in session_memory:
        msgs.append({"role":"user","content":mem["user"]})
        msgs.append({"role":"assistant","content":mem["response"]})
    msgs.append({"role":"user","content":user_ctx})

    return _llm_call(msgs, temperature=0.9, max_tokens=2048)

# ─── PROCESSAMENTO PRINCIPAL ─────────────────────────────────────────────────────

async def process(message, session_id, force_squad=None):
    # 1. Detecta intenção de execução
    intent = detect_intent(message)

    if intent["intent"] != "consult":
        result = await execute_intent(intent, message, session_id)
        if result:
            save_memory(session_id, result["squad"], result["chief"], message, result["response"])
            return result

    # 2. Consulta especialista LLM
    if force_squad and force_squad in SQUADS:
        squad_name = force_squad
    else:
        squad_name, score = route(message)
        if score == 0:
            squad_name = await route_llm(message)

    mem = load_memory(session_id)
    response = await consult(squad_name, message, mem)
    save_memory(session_id, squad_name, SQUADS[squad_name]["chief"], message, response)
    return {"squad":squad_name,"chief":SQUADS[squad_name]["chief"],"response":response}

# ─── INTERFACE ───────────────────────────────────────────────────────────────────

async def chat():
    session_id = str(uuid.uuid4())[:8]
    print(f"\n{'='*60}")
    print(f"  ELI v4.0 | Sessao {session_id}")
    print(f"  CAMADA 1: Factory + Browser (execucao real)")
    print(f"  CAMADA 2: 152 consultores LLM")
    print(f"  Comandos: sair | squads | agentes | @squad msg")
    print(f"  Execucao: 'abra o site X' | 'screenshot X' | 'salve [resultado]'")
    print(f"{'='*60}\n")

    while True:
        try: user = input("Voce: ").strip()
        except (EOFError, KeyboardInterrupt): break
        if not user: continue
        if user.lower() in ["sair","exit"]: break
        if user.lower() == "squads":
            for k in SQUADS: print(f"  {k}")
            continue
        if user.lower() == "agentes":
            agents = await factory_list()
            for a in agents: print(f"  {a['id']} [{a['status']}]")
            continue

        force = None
        msg = user
        if user.startswith("@"):
            parts = user.split(" ",1)
            c = parts[0][1:]
            if c in SQUADS:
                force = c
                msg = parts[1] if len(parts)>1 else "ola"

        r = await process(msg, session_id, force)
        print(f"\n[{r['squad']} → {r['chief']}]")
        print(f"ELI: {r['response']}\n")

async def single(msg):
    sid = str(uuid.uuid4())[:8]
    return await process(msg, sid)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        msg = " ".join(sys.argv[1:])
        r = asyncio.run(single(msg))
        print(f"\n[{r['squad']} → {r['chief']}]\n{r['response']}")
    else:
        asyncio.run(chat())



async def evaluate_output(objective, output, squad):
    try:
        prompt = (
            "Avaliador senior. Criterios rigorosos:\n"
            "10=perfeito,acionavel,completo,sem gaps\n"
            "9=excelente,falta detalhe menor\n"
            "8=bom mas generico\n7=aceitavel sem profundidade\n"
            "Retorne APENAS JSON sem markdown:\n"
            '{"score":9,"reason":"motivo","improvement":"melhoria"}\n\n'
            f"OBJETIVO: {objective[:400]}\n"
            f"SQUAD: {squad}\n"
            f"OUTPUT: {output[:1500]}"
        )
        r = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"user","content":prompt}],
            temperature=0.1, max_tokens=200
        )
        raw = r.choices[0].message.content.strip()
        for f in ["```json","```"]: raw = raw.removeprefix(f).removesuffix(f).strip()
        import re as _re
        m = _re.search(r'\{[^{}]+\}', raw, _re.DOTALL)
        if m: raw = m.group()
        return json.loads(raw)
    except Exception:
        return {"score": 7, "reason": "avaliacao indisponivel", "improvement": "mais detalhes praticos"}

async def evaluate_output(objective, output, squad):
    try:
        prompt = (
            "Avaliador senior. Criterios rigorosos:\n"
            "10=perfeito,acionavel,completo,sem gaps\n"
            "9=excelente,falta detalhe menor\n"
            "8=bom mas generico\n7=aceitavel sem profundidade\n"
            "Retorne APENAS JSON sem markdown:\n"
            '{"score":9,"reason":"motivo","improvement":"melhoria"}\n\n'
            f"OBJETIVO: {objective[:400]}\n"
            f"SQUAD: {squad}\n"
            f"OUTPUT: {output[:1500]}"
        )
        r = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"user","content":prompt}],
            temperature=0.1, max_tokens=200
        )
        raw = r.choices[0].message.content.strip()
        for f in ["```json","```"]: raw = raw.removeprefix(f).removesuffix(f).strip()
        import re as _re
        m = _re.search(r'\{[^{}]+\}', raw, _re.DOTALL)
        if m: raw = m.group()
        return json.loads(raw)
    except Exception:
        return {"score": 7, "reason": "avaliacao indisponivel", "improvement": "mais detalhes praticos"}

# ─── TOOL: CRIAR PERFIS ──────────────────────────────────────────────────────
def criar_perfis_redes(marca, nicho, tom="profissional", site="", email=""):
    redes = [
        {"rede":"Instagram","user":marca.lower().replace(" ","."),"bio":f"{marca} | {nicho}\n{tom}\n{site}","dica":"Emojis, hashtag no comentario, link na bio"},
        {"rede":"TikTok","user":marca.lower().replace(" ","_"),"bio":f"{marca} | {nicho}\n{site}","dica":"Bio curta, CTA direto"},
        {"rede":"LinkedIn","user":marca.lower().replace(" ","-"),"bio":f"{marca} - {nicho}. {tom}. {email}","dica":"Descricao completa, especialidades, site"},
        {"rede":"YouTube","user":marca.lower().replace(" ",""),"bio":f"Canal de {marca}. {nicho}.\n{email}\n{site}","dica":"About detalhado, links, email comercial"},
        {"rede":"Facebook","user":marca.lower().replace(" ",""),"bio":f"{marca} - {nicho}. {tom}.","dica":"Pagina comercial, categoria, CTA"},
        {"rede":"Twitter/X","user":marca.lower().replace(" ",""),"bio":f"{marca} | {nicho} | {site}","dica":"Bio objetiva, fixar tweet de apresentacao"},
        {"rede":"Pinterest","user":marca.lower().replace(" ",""),"bio":f"{marca} | {nicho} | {tom}","dica":"Conta comercial, boards por tema"},
        {"rede":"Threads","user":marca.lower().replace(" ","."),"bio":f"{marca} | {nicho}\n{site}","dica":"Conectado ao Instagram, bio identica"},
    ]
    rel = f"# Perfis — {marca}\n\n"
    for r in redes:
        rel += f"## {r['rede']}\n- **@{r['user']}**\n- Bio: {r['bio']}\n- Dica: {r['dica']}\n\n"
    return rel
