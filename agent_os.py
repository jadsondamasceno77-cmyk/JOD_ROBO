#!/usr/bin/env python3
"""
Agent OS v3 — LangGraph ReAct + Critic loop
Correções:
  1. ToolNode CONECTADO ao grafo (tools executam de fato)
  2. Researcher usa ReAct real: agent → tools → agent → ... (sem double-call)
  3. LLM singleton + MAX_ATTEMPTS=2 (reduz latência)
  4. MemorySaver com thread_id por session (memória persistente entre chamadas)
"""
import os
import json
import operator
import httpx
from typing import List, Optional, Annotated
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

# ─── Config ───────────────────────────────────────────────────────────────────
_ELI     = "http://localhost:37779"
_N8N     = "http://localhost:5678"
_TOKEN   = os.getenv("JOD_TRUST_MANIFEST", "jod_robo_trust_2026_secure")
_N8N_KEY = os.getenv("N8N_API_KEY", (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJzdWIiOiIxNTVjMmNiMi02MjY0LTRlNTgtYTQ0OS1kZmNmZDk4YjQ1ZmYiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiMjYyN2E0Y2ItYzNhNy00Y2E5LTg1YzgtNDI4ZDczMmNkODdhIiwiaWF0IjoxNzc0NDkzMTgzfQ"
    ".b6VGcXvFU5TjzYr8YUcz8xpcISJNBRRoU5hZhL8xn8s"
))

# FIX 3 — LLM singleton: criado uma vez, reutilizado em todas as chamadas
_LLM_INSTANCE: Optional[ChatGroq] = None

def _llm() -> ChatGroq:
    global _LLM_INSTANCE
    if _LLM_INSTANCE is None:
        _LLM_INSTANCE = ChatGroq(
            model="llama-3.3-70b-versatile",
            api_key=os.getenv("GROQ_API_KEY", ""),
            temperature=0.1,
        )
    return _LLM_INSTANCE

# FIX 4 — MemorySaver singleton: persiste estado entre chamadas (mesmo processo)
_MEMORY = MemorySaver()

# ─── LangChain Tools ─────────────────────────────────────────────────────────

@tool
async def eli_consultar(message: str) -> str:
    """Consulta os 162 agentes especializados da ELI API. Use para pesquisa, análise e execução de tarefas complexas."""
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.post(f"{_ELI}/chat",
            headers={"x-jod-token": _TOKEN, "Content-Type": "application/json"},
            json={"message": message, "session_id": "agent-os"})
        return json.dumps(r.json(), ensure_ascii=False)

@tool
async def n8n_listar_workflows() -> str:
    """Lista todos os workflows ativos no n8n. Use para inspecionar o estado do sistema."""
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.get(f"{_N8N}/api/v1/workflows",
            headers={"X-N8N-API-KEY": _N8N_KEY})
        return json.dumps(r.json(), ensure_ascii=False)

@tool
async def vault_backup(workflow_id: str, workflow_name: str, workflow_json: dict) -> str:
    """Faz backup imutável de um workflow no vault git. Use após qualquer alteração importante."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.post(f"{_ELI}/vault/backup",
            headers={"x-jod-token": _TOKEN, "Content-Type": "application/json"},
            json={"workflow_id": workflow_id, "workflow_name": workflow_name, "workflow_json": workflow_json})
        return json.dumps(r.json(), ensure_ascii=False)

@tool
async def self_heal(workflow_id: str, error_log: str, broken_node_name: str) -> str:
    """Auto-cura: analisa erro e gera patch para um nó quebrado do n8n."""
    async with httpx.AsyncClient(timeout=20.0) as c:
        r = await c.post(f"{_ELI}/self-healing",
            headers={"x-jod-token": _TOKEN, "Content-Type": "application/json"},
            json={"workflow_id": workflow_id, "error_log": error_log, "broken_node_name": broken_node_name})
        return json.dumps(r.json(), ensure_ascii=False)

@tool
async def rollback(workflow_id: str) -> str:
    """Faz rollback assíncrono de um workflow para a versão anterior no vault git."""
    async with httpx.AsyncClient(timeout=20.0) as c:
        r = await c.post(f"{_ELI}/vault/rollback",
            headers={"x-jod-token": _TOKEN, "Content-Type": "application/json"},
            json={"workflow_id": workflow_id})
        return json.dumps(r.json(), ensure_ascii=False)

from eli_phases import ALL_ELI_TOOLS
TOOLS = [eli_consultar, n8n_listar_workflows, vault_backup, self_heal, rollback] + ALL_ELI_TOOLS

# ─── Pydantic Schema ──────────────────────────────────────────────────────────

class AgentOutput(BaseModel):
    content: str = Field(description="Conteúdo gerado ou resultado da execução")
    is_valid: bool = Field(description="True se a tarefa foi executada com sucesso")
    revision_notes: List[str] = Field(
        default_factory=list,
        description="Problemas encontrados pelo crítico"
    )

# ─── Graph State ──────────────────────────────────────────────────────────────
# FIX 1+2 — messages usa add_messages para o ReAct loop funcionar com ToolNode

class AgentState(TypedDict):
    task: str
    messages: Annotated[list, add_messages]   # ReAct message chain
    last_output: Optional[AgentOutput]
    history: Annotated[List[dict], operator.add]
    attempts: int

# ─── Nodes ───────────────────────────────────────────────────────────────────

_SYSTEM = SystemMessage(content=(
    "Você é o ROBÔ MÃE do JOD_ROBO v5.0 — executor autônomo de negócios digitais.\n\n"
    "5 FASES ELI DISPONÍVEIS:\n"
    "FASE 1 — GESTÃO 24/7: atendimento_24h | agenda_pessoal | posicionamento_nicho\n"
    "FASE 2 — ESTRATÉGIA: reuniao_equipe_conteudo | roteiro_conteudo | storytelling_personal_branding | copywriting_produto | growth_estrategias\n"
    "FASE 3 — ATIVOS: gerar_identidade_visual | gerar_landing_page | configurar_perfil_autoridade | gerar_pagina_vendas\n"
    "FASE 4 — TRAÇÃO: estrategia_trafego | panfletagem_digital | roteiro_engajamento | triagem_interessados\n"
    "FASE 5 — CONVERSÃO: oferta_direta_qualificados | script_remarketing | automacao_atendimento_vendas | automacao_checkout\n\n"
    "INFRA: eli_consultar (162 agentes) | n8n_listar_workflows | vault_backup | self_heal | rollback\n\n"
    "REGRA: use sempre as tools. Entregue resultados concretos e prontos para uso. Zero enrolação."
))

def researcher_node(state: AgentState) -> dict:
    """
    FIX 1+2 — ReAct real: uma única chamada LLM com tools bound.
    O ToolNode executa as tools se o LLM as invocar (edge condicional).
    Sem double-call: uma fase só.
    """
    llm = _llm().bind_tools(TOOLS)

    # Primeira iteração do ciclo: inicializa mensagens
    if not state.get("messages"):
        revision_ctx = ""
        if state.get("last_output") and not state["last_output"].is_valid:
            notes = "\n".join(f"- {n}" for n in state["last_output"].revision_notes)
            revision_ctx = f"\n\nREVISÃO OBRIGATÓRIA:\n{notes}"
        msgs = [_SYSTEM, HumanMessage(content=f"Execute: {state['task']}{revision_ctx}")]
        response = llm.invoke(msgs)
        return {"messages": msgs + [response]}

    # Iteração subsequente (após ToolNode executou tools)
    response = llm.invoke(state["messages"])
    return {"messages": [response]}


def should_use_tools(state: AgentState) -> str:
    """FIX 1 — verifica se o LLM quer chamar tools. Se sim → ToolNode executa."""
    last = state["messages"][-1] if state.get("messages") else None
    if last and hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return "structure"


def structure_node(state: AgentState) -> dict:
    """
    FIX 2 — converte a cadeia de mensagens ReAct em AgentOutput estruturado.
    Chamado SOMENTE quando o LLM não tem mais tool_calls (ReAct concluído).
    """
    llm = _llm().with_structured_output(AgentOutput)

    # Coleta o conteúdo da última resposta do LLM
    last_content = next(
        (m.content for m in reversed(state["messages"])
         if hasattr(m, "content") and m.content
         and not (hasattr(m, "tool_calls") and m.tool_calls)),
        "sem conteúdo"
    )

    result: AgentOutput = llm.invoke(
        f"TAREFA: {state['task']}\n\n"
        f"RESULTADO DA EXECUÇÃO:\n{last_content}\n\n"
        f"Estruture em AgentOutput. is_valid=true se a tarefa foi executada com sucesso."
    )
    return {
        "last_output": result,
        "history": [{"node": "researcher", "is_valid": result.is_valid}],
        "attempts": state.get("attempts", 0) + 1,
    }


def critic_node(state: AgentState) -> dict:
    """Valida o resultado. Aprova ou gera revision_notes específicas."""
    llm = _llm().with_structured_output(AgentOutput)

    result: AgentOutput = llm.invoke(
        f"Crítico técnico sênior. Avalie se a tarefa foi executada corretamente.\n\n"
        f"TAREFA: {state['task']}\n\n"
        f"RESULTADO:\n{state['last_output'].content}\n\n"
        f"Aprovado: is_valid=True, revision_notes=[]\n"
        f"Reprovado: is_valid=False, revision_notes com ações específicas a corrigir.\n"
        f"Mantenha content idêntico ao recebido."
    )
    return {
        "last_output": result,
        "history": [{"node": "critic", "is_valid": result.is_valid, "notes": result.revision_notes}],
    }


def inject_revision(state: AgentState) -> dict:
    """Injeta notas do crítico como nova mensagem e limpa messages para novo ciclo."""
    notes = "\n".join(f"- {n}" for n in state["last_output"].revision_notes)
    # Retorna mensagens zeradas + nova instrução de revisão
    return {
        "messages": [
            _SYSTEM,
            HumanMessage(content=(
                f"Execute novamente: {state['task']}\n\n"
                f"REVISÃO OBRIGATÓRIA — corrija estes pontos:\n{notes}"
            ))
        ]
    }


def router_node(state: AgentState) -> str:
    """FIX 3 — MAX_ATTEMPTS reduzido para 2 (latência). Loop ou finaliza."""
    MAX_ATTEMPTS = 2
    if state["last_output"].is_valid or state.get("attempts", 0) >= MAX_ATTEMPTS:
        return "end"
    return "retry"


# ─── Build Graph ──────────────────────────────────────────────────────────────

def build_graph():
    """
    Grafo corrigido:
    researcher → should_use_tools?
      → "tools": ToolNode (executa tools reais) → researcher  [ReAct loop]
      → "structure": structure_node → critic → router
          → "retry": inject_revision → researcher  [ciclo correção]
          → "end": END
    """
    g = StateGraph(AgentState)

    # FIX 1 — ToolNode conectado como nó real no grafo
    g.add_node("researcher", researcher_node)
    g.add_node("tools", ToolNode(TOOLS))
    g.add_node("structure", structure_node)
    g.add_node("critic", critic_node)
    g.add_node("inject_revision", inject_revision)

    g.set_entry_point("researcher")

    # ReAct loop: researcher ↔ tools até LLM parar de chamar tools
    g.add_conditional_edges("researcher", should_use_tools, {
        "tools": "tools",
        "structure": "structure",
    })
    g.add_edge("tools", "researcher")

    # Fluxo pós-pesquisa
    g.add_edge("structure", "critic")
    g.add_conditional_edges("critic", router_node, {
        "retry": "inject_revision",
        "end": END,
    })
    g.add_edge("inject_revision", "researcher")

    # FIX 4 — MemorySaver: persiste estado por thread_id (session_id)
    return g.compile(checkpointer=_MEMORY)


# ─── Public entrypoint ────────────────────────────────────────────────────────

async def run_agent_os(task: str, session_id: str = "default") -> dict:
    """
    Executa o Agent OS.
    session_id mantém contexto entre chamadas (memória por sessão).
    """
    graph = build_graph()
    config = {"configurable": {"thread_id": session_id}}

    initial: AgentState = {
        "task": task,
        "messages": [],
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
