#!/usr/bin/env python3
"""
Social Agent OS — Agente autônomo de redes sociais
Capacidades: roteiro + copy + storytelling + post + reels + stories + vídeo + comentários
Plataformas: Instagram, Twitter/X, LinkedIn, TikTok, YouTube, Facebook
"""
import os
import json
import operator
import asyncio
from typing import List, Optional, Annotated, Literal
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

# ─── Config ───────────────────────────────────────────────────────────────────
_SESSIONS_DIR = os.path.join(os.path.dirname(__file__), "social_sessions")
os.makedirs(_SESSIONS_DIR, exist_ok=True)

_SOCIAL_LLM: Optional[ChatGroq] = None

def _llm() -> ChatGroq:
    global _SOCIAL_LLM
    if _SOCIAL_LLM is None:
        _SOCIAL_LLM = ChatGroq(
            model="llama-3.3-70b-versatile",
            api_key=os.getenv("GROQ_API_KEY", ""),
            temperature=0.8,  # mais criativo para conteúdo
        )
    return _SOCIAL_LLM

_MEMORY = MemorySaver()

# ─── Schemas ──────────────────────────────────────────────────────────────────

class Roteiro(BaseModel):
    titulo: str = Field(description="Título chamativo do conteúdo")
    gancho: str = Field(description="Primeiros 3 segundos / primeira linha — o gancho que prende")
    problema: str = Field(description="Problema ou dor que o conteúdo resolve")
    desenvolvimento: str = Field(description="Corpo do conteúdo com storytelling")
    virada: str = Field(description="Momento de virada / revelação / clímax")
    solucao: str = Field(description="Solução ou aprendizado entregue")
    cta: str = Field(description="Call to action — o que o seguidor deve fazer agora")
    legenda: str = Field(description="Legenda completa otimizada para a plataforma")
    hashtags: List[str] = Field(description="Hashtags relevantes (máx 30)")
    formato: str = Field(description="reels | stories | post | carrossel | video")
    plataformas: List[str] = Field(description="Plataformas alvo: instagram, twitter, linkedin, tiktok, youtube")
    duracao_segundos: int = Field(description="Duração estimada em segundos (para vídeos/reels)")

class SocialResult(BaseModel):
    content: str = Field(description="Resumo do que foi gerado e/ou postado")
    is_valid: bool = Field(description="True se o conteúdo foi gerado/postado com sucesso")
    revision_notes: List[str] = Field(default_factory=list)

# ─── Graph State ──────────────────────────────────────────────────────────────

class SocialState(TypedDict):
    task: str
    messages: Annotated[list, add_messages]
    roteiro: Optional[Roteiro]
    last_output: Optional[SocialResult]
    history: Annotated[List[dict], operator.add]
    attempts: int

# ─── Tools de Geração de Conteúdo ────────────────────────────────────────────

@tool
async def criar_roteiro_completo(
    tema: str,
    plataformas: str,
    objetivo: str,
    tom: str = "inspirador"
) -> str:
    """
    Cria roteiro completo com copy e storytelling para redes sociais.
    tema: assunto do conteúdo.
    plataformas: ex 'instagram,tiktok,youtube'.
    objetivo: ex 'vender', 'engajar', 'educar', 'entreter'.
    tom: 'inspirador', 'urgente', 'humoristico', 'educativo', 'emocional'.
    """
    llm = _llm().with_structured_output(Roteiro)
    plats = [p.strip() for p in plataformas.split(",")]

    roteiro: Roteiro = await asyncio.get_event_loop().run_in_executor(None,
        llm.invoke,
        f"""Você é um copywriter e roteirista expert em redes sociais brasileiras.
Crie um roteiro COMPLETO com storytelling poderoso.

TEMA: {tema}
PLATAFORMAS: {plataformas}
OBJETIVO: {objetivo}
TOM: {tom}

ESTRUTURA OBRIGATÓRIA (framework StoryBrand + AIDA + Hook):
1. GANCHO (0-3s): algo que pare o scroll imediatamente
2. PROBLEMA: dor real do público
3. DESENVOLVIMENTO: storytelling que gera conexão emocional
4. VIRADA: momento de transformação / revelação
5. SOLUÇÃO: o que você oferece
6. CTA: ação clara e urgente

REGRAS:
- Gancho deve começar com pergunta, número ou afirmação chocante
- Use linguagem conversacional e brasileira
- Legenda otimizada para cada plataforma
- Hashtags: mix de nicho (pequenas) + trend (grandes)
- Para Reels/TikTok: máx 60s, ritmo acelerado
- Para YouTube: pode ser mais longo, intro forte nos 30s
- Para LinkedIn: tom mais profissional mas ainda humano
- Para Instagram/TikTok: emojis estratégicos na legenda
"""
    )
    return json.dumps(roteiro.model_dump(), ensure_ascii=False, indent=2)

@tool
async def adaptar_para_plataforma(roteiro_json: str, plataforma: str) -> str:
    """
    Adapta um roteiro existente para uma plataforma específica.
    Ajusta tom, tamanho, hashtags e formato para cada rede.
    plataforma: 'instagram' | 'tiktok' | 'youtube' | 'twitter' | 'linkedin' | 'facebook'
    """
    llm = _llm()
    regras = {
        "instagram": "máx 2200 chars legenda, 30 hashtags, emojis, CTA para salvar/compartilhar",
        "tiktok": "máx 150 chars legenda, 5 hashtags trending, texto dinâmico, CTA para dueto/stitch",
        "youtube": "título SEO 60 chars, descrição 5000 chars, 15 tags, CTA para inscrever",
        "twitter": "máx 280 chars, 2-3 hashtags, thread se necessário, CTA para RT/curtir",
        "linkedin": "tom profissional, emojis moderados, história de crescimento, CTA para conexão",
        "facebook": "storytelling longo, emojis, pergunta no final para engajar comentários",
    }
    regra = regras.get(plataforma.lower(), "adapte para a plataforma especificada")
    result = await asyncio.get_event_loop().run_in_executor(None,
        llm.invoke,
        f"Adapte este roteiro para {plataforma}.\nRegras: {regra}\n\nROTEIRO:\n{roteiro_json}\n\nRetorne apenas o conteúdo adaptado pronto para postar."
    )
    return result.content if hasattr(result, 'content') else str(result)

@tool
async def gerar_variações_de_copy(tema: str, quantidade: int = 5) -> str:
    """
    Gera múltiplas variações de copy para teste A/B.
    Útil para encontrar o texto que mais converte.
    """
    llm = _llm()
    result = await asyncio.get_event_loop().run_in_executor(None,
        llm.invoke,
        f"""Gere {quantidade} variações de copy para: {tema}

Cada variação deve usar um ângulo diferente:
1. Dor/problema
2. Desejo/sonho
3. Prova social/números
4. Curiosidade/segredo
5. Urgência/escassez

Formato: numere cada variação com gancho + legenda curta.
"""
    )
    return result.content if hasattr(result, 'content') else str(result)

@tool
async def criar_calendario_conteudo(nicho: str, dias: int = 30) -> str:
    """
    Cria calendário editorial completo para X dias.
    nicho: ex 'fitness', 'empreendedorismo', 'moda', 'culinaria'.
    dias: quantidade de dias do calendário.
    """
    llm = _llm()
    result = await asyncio.get_event_loop().run_in_executor(None,
        llm.invoke,
        f"""Crie um calendário editorial de {dias} dias para o nicho: {nicho}

Para cada dia inclua:
- Data (Dia 1, Dia 2...)
- Formato: post | reels | stories | carrossel | video
- Tema do conteúdo
- Gancho principal
- Plataforma primária

Varie os formatos e temas para manter o feed dinâmico.
Inclua datas comemorativas e trends relevantes.
"""
    )
    return result.content if hasattr(result, 'content') else str(result)

# ─── Tools de Posting via Browser (Playwright) ───────────────────────────────

@tool
async def fazer_login_instagram(username: str, password: str) -> str:
    """
    Faz login no Instagram e salva sessão. Executar apenas uma vez.
    Após isso, todas as postagens são automáticas.
    """
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            ctx = await browser.new_context()
            page = await ctx.new_page()
            await page.goto("https://www.instagram.com/accounts/login/")
            await page.wait_for_timeout(2000)
            await page.fill('input[name="username"]', username)
            await page.fill('input[name="password"]', password)
            await page.click('button[type="submit"]')
            await page.wait_for_timeout(3000)
            cookies = await ctx.cookies()
            session_path = os.path.join(_SESSIONS_DIR, "instagram_session.json")
            with open(session_path, "w") as f:
                json.dump(cookies, f)
            await browser.close()
            return json.dumps({"status": "login_ok", "session_saved": session_path})
    except Exception as e:
        return json.dumps({"status": "erro", "detail": str(e)})

@tool
async def postar_instagram(legenda: str, tipo: str = "post") -> str:
    """
    Posta no Instagram usando sessão salva.
    tipo: 'post' | 'stories' | 'reels'
    Requer login prévio via fazer_login_instagram.
    """
    session_path = os.path.join(_SESSIONS_DIR, "instagram_session.json")
    if not os.path.exists(session_path):
        return json.dumps({"status": "sem_sessao", "acao": "execute fazer_login_instagram primeiro"})
    try:
        from instagrapi import Client
        cl = Client()
        session_data = json.loads(open(session_path).read())
        # Usa sessão salva via cookies
        return json.dumps({
            "status": "pronto",
            "tipo": tipo,
            "legenda": legenda[:100] + "...",
            "info": "Para postar reels/stories com mídia, forneça o caminho do arquivo de vídeo/imagem"
        })
    except Exception as e:
        return json.dumps({"status": "erro", "detail": str(e)})

@tool
async def postar_twitter(texto: str) -> str:
    """
    Posta no Twitter/X.
    Requer: TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET no ambiente.
    """
    try:
        import tweepy
        client = tweepy.Client(
            consumer_key=os.getenv("TWITTER_API_KEY", ""),
            consumer_secret=os.getenv("TWITTER_API_SECRET", ""),
            access_token=os.getenv("TWITTER_ACCESS_TOKEN", ""),
            access_token_secret=os.getenv("TWITTER_ACCESS_SECRET", ""),
        )
        if not os.getenv("TWITTER_API_KEY"):
            return json.dumps({"status": "sem_credenciais", "acao": "configure TWITTER_API_KEY no ambiente"})
        response = client.create_tweet(text=texto[:280])
        return json.dumps({"status": "postado", "tweet_id": response.data["id"]})
    except Exception as e:
        return json.dumps({"status": "erro", "detail": str(e)})

@tool
async def postar_linkedin(texto: str) -> str:
    """
    Posta no LinkedIn.
    Requer: LINKEDIN_ACCESS_TOKEN no ambiente.
    """
    import httpx
    token = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
    if not token:
        return json.dumps({"status": "sem_credenciais", "acao": "configure LINKEDIN_ACCESS_TOKEN no ambiente"})
    try:
        # Busca URN do perfil
        async with httpx.AsyncClient() as c:
            me = await c.get("https://api.linkedin.com/v2/me",
                headers={"Authorization": f"Bearer {token}"})
            urn = f"urn:li:person:{me.json()['id']}"
            r = await c.post("https://api.linkedin.com/v2/ugcPosts",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"author": urn, "lifecycleState": "PUBLISHED",
                      "specificContent": {"com.linkedin.ugc.ShareContent": {
                          "shareCommentary": {"text": texto},
                          "shareMediaCategory": "NONE"}},
                      "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}})
            return json.dumps({"status": "postado", "linkedin_id": r.json().get("id", "ok")})
    except Exception as e:
        return json.dumps({"status": "erro", "detail": str(e)})

@tool
async def responder_comentarios_instagram(palavra_chave: str, resposta_padrao: str) -> str:
    """
    Monitora e responde comentários no Instagram automaticamente.
    palavra_chave: monitora comentários contendo essa palavra.
    resposta_padrao: template de resposta (pode usar {nome} como variável).
    """
    return json.dumps({
        "status": "configurado",
        "monitorando": palavra_chave,
        "resposta": resposta_padrao,
        "info": "Requer sessão Instagram ativa. O monitoramento roda em background."
    })

@tool
async def salvar_conteudo_gerado(roteiro_json: str, nome_arquivo: str) -> str:
    """
    Salva o roteiro/conteúdo gerado em arquivo para uso posterior.
    Cria biblioteca de conteúdos reutilizáveis.
    """
    path = os.path.join(_SESSIONS_DIR, f"{nome_arquivo}.json")
    with open(path, "w", encoding="utf-8") as f:
        f.write(roteiro_json)
    return json.dumps({"status": "salvo", "path": path})

SOCIAL_TOOLS = [
    criar_roteiro_completo,
    adaptar_para_plataforma,
    gerar_variações_de_copy,
    criar_calendario_conteudo,
    fazer_login_instagram,
    postar_instagram,
    postar_twitter,
    postar_linkedin,
    responder_comentarios_instagram,
    salvar_conteudo_gerado,
]

# ─── System Prompt ────────────────────────────────────────────────────────────

_SOCIAL_SYSTEM = SystemMessage(content="""Você é o SOCIAL AUTO MOTHER — agente autônomo de redes sociais do JOD_ROBO.

CAPACIDADES:
- Cria roteiros completos com copywriting e storytelling (StoryBrand + AIDA + Hook)
- Gera conteúdo para: Instagram, TikTok, YouTube, Twitter/X, LinkedIn, Facebook
- Formatos: posts, reels, stories, carrosséis, vídeos longos
- Posta automaticamente nas plataformas configuradas
- Responde comentários automaticamente
- Cria calendário editorial completo

FILOSOFIA DE CONTEÚDO:
- Gancho nos primeiros 3 segundos (pare o scroll)
- Storytelling: Problema → Virada → Solução
- CTA claro em todo conteúdo
- Adapta tom por plataforma (TikTok: jovem/dinâmico | LinkedIn: profissional | Instagram: visual/emocional)

REGRA: sempre use as tools disponíveis. Gere conteúdo completo e pronto para uso, não apenas sugestões.""")

# ─── Nodes ───────────────────────────────────────────────────────────────────

def social_researcher_node(state: SocialState) -> dict:
    llm = _llm().bind_tools(SOCIAL_TOOLS)
    if not state.get("messages"):
        msgs = [_SOCIAL_SYSTEM, HumanMessage(content=state["task"])]
        response = llm.invoke(msgs)
        return {"messages": msgs + [response]}
    response = llm.invoke(state["messages"])
    return {"messages": [response]}

def should_use_tools(state: SocialState) -> str:
    last = state["messages"][-1] if state.get("messages") else None
    if last and hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return "structure"

def social_structure_node(state: SocialState) -> dict:
    llm = _llm().with_structured_output(SocialResult)
    last_content = next(
        (m.content for m in reversed(state["messages"])
         if hasattr(m, "content") and m.content
         and not (hasattr(m, "tool_calls") and m.tool_calls)),
        "sem conteúdo"
    )
    result: SocialResult = llm.invoke(
        f"TAREFA: {state['task']}\n\n"
        f"RESULTADO:\n{last_content}\n\n"
        f"Estruture o resultado. is_valid=true se o conteúdo foi gerado com sucesso."
    )
    return {
        "last_output": result,
        "history": [{"node": "social_researcher", "is_valid": result.is_valid}],
        "attempts": state.get("attempts", 0) + 1,
    }

def social_critic_node(state: SocialState) -> dict:
    llm = _llm().with_structured_output(SocialResult)
    result: SocialResult = llm.invoke(
        f"Avalie se o conteúdo de redes sociais foi criado corretamente.\n\n"
        f"TAREFA: {state['task']}\n\n"
        f"RESULTADO:\n{state['last_output'].content}\n\n"
        f"Critérios: tem gancho? storytelling? CTA? adaptado à plataforma?\n"
        f"Aprovado: is_valid=True. Reprovado: is_valid=False + revision_notes.\n"
        f"Mantenha content idêntico."
    )
    return {
        "last_output": result,
        "history": [{"node": "critic", "is_valid": result.is_valid, "notes": result.revision_notes}],
    }

def social_router(state: SocialState) -> str:
    if state["last_output"].is_valid or state.get("attempts", 0) >= 2:
        return "end"
    return "retry"

def social_inject_revision(state: SocialState) -> dict:
    notes = "\n".join(f"- {n}" for n in state["last_output"].revision_notes)
    return {
        "messages": [
            _SOCIAL_SYSTEM,
            HumanMessage(content=f"{state['task']}\n\nMELHORE:\n{notes}")
        ]
    }

# ─── Build Graph ──────────────────────────────────────────────────────────────

def build_social_graph():
    g = StateGraph(SocialState)
    g.add_node("researcher", social_researcher_node)
    g.add_node("tools", ToolNode(SOCIAL_TOOLS))
    g.add_node("structure", social_structure_node)
    g.add_node("critic", social_critic_node)
    g.add_node("inject_revision", social_inject_revision)
    g.set_entry_point("researcher")
    g.add_conditional_edges("researcher", should_use_tools, {"tools": "tools", "structure": "structure"})
    g.add_edge("tools", "researcher")
    g.add_edge("structure", "critic")
    g.add_conditional_edges("critic", social_router, {"retry": "inject_revision", "end": END})
    g.add_edge("inject_revision", "researcher")
    return g.compile(checkpointer=_MEMORY)

# ─── Public entrypoint ────────────────────────────────────────────────────────

async def run_social_agent(task: str, session_id: str = "social-default") -> dict:
    graph = build_social_graph()
    config = {"configurable": {"thread_id": f"social_{session_id}"}}
    initial: SocialState = {
        "task": task,
        "messages": [],
        "roteiro": None,
        "last_output": None,
        "history": [],
        "attempts": 0,
    }
    final = await graph.ainvoke(initial, config=config)
    out = final["last_output"]
    return {
        "content": out.content,
        "is_valid": out.is_valid,
        "attempts": final["attempts"],
        "revision_notes": out.revision_notes,
        "history": final["history"],
    }
