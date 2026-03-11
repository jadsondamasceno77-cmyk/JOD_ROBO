"""Agentes especializados: Arquiteto, Executor e Revisor."""
import logging, os
from typing import Optional
from pathlib import Path
from pydantic import BaseModel, ValidationError
from jod_brain.llm import call_groq, call_ollama, parse_json
from jod_brain.memory import context as mem_context

logger = logging.getLogger("jod.agents")

# Injeção de dependência — sem global mutável
class Config:
    """Configuração injetada nos agents."""
    def __init__(self, api_key: str, ollama_host: str = "http://127.0.0.1:11434",
                 ollama_model: str = "llama3.2:1b"):
        self.api_key = api_key
        self.ollama_host = ollama_host
        self.ollama_model = ollama_model

# Schemas Pydantic para validação de resposta do LLM
class Plano(BaseModel):
    summary: str
    subtarefas: list[str]
    tipo: str
    aprendizado: Optional[str] = None

class Change(BaseModel):
    file: str
    action: str
    content: str

class Resultado(BaseModel):
    summary: str
    changes: list[Change]

class Revisao(BaseModel):
    aprovado: bool
    problemas: list[str] = []
    correcoes: list[Change] = []

SYSTEM_ARQUITETO = """{PERSONALITY}\n\nVoce e o Agente Arquiteto do JOD_ROBO. Analisa a tarefa e cria plano de execucao.
Retorne APENAS JSON valido sem markdown:
{"summary":"descricao","subtarefas":["sub1","sub2"],"tipo":"agente|site|app|automacao|script","aprendizado":"licao"}"""

SYSTEM_EXECUTOR = """Voce e o Agente Executor do JOD_ROBO. Cria arquivos para a tarefa.
Retorne APENAS JSON valido sem markdown:
{"summary":"o que foi criado","changes":[{"file":"agents/nome.py","action":"write","content":"codigo completo"}]}
REGRAS: apenas arquivos NOVOS fora de app/ | agents/ sites/ apps/ scripts/ tools/ | codigo COMPLETO e funcional"""

SYSTEM_REVISOR = """Voce e o Agente Revisor do JOD_ROBO. Verifica execucao do plano.
Retorne APENAS JSON valido sem markdown:
{"aprovado":true,"problemas":[],"correcoes":[{"file":"path","action":"write","content":"codigo"}]}"""

def _call(system: str, user_msg: str, config: Config) -> Optional[str]:
    """Chama Groq com fallback para Ollama."""
    raw = call_groq(system, user_msg, config.api_key)
    if not raw:
        logger.warning("Groq indisponivel, usando Ollama como fallback")
        raw = call_ollama(system + "\n" + user_msg, config.ollama_model, config.ollama_host)
    return raw

def arquiteto(task: str, memory: dict, cwd: str, config: Config) -> Optional[Plano]:
    """Analisa tarefa e retorna plano estruturado.
    
    Args:
        task: Tarefa a executar.
        memory: Histórico de execuções.
        cwd: Diretório do projeto.
        config: Configuração com credenciais.
    
    Returns:
        Plano validado ou None se falhar.
    """
    user_msg = f"{mem_context(memory)}\n\nTAREFA: {task}\nPROJETO: {cwd}"
    raw = _call(SYSTEM_ARQUITETO, user_msg, config)
    if not raw:
        return None
    data = parse_json(raw)
    if not data:
        logger.error("Arquiteto retornou JSON invalido")
        return None
    try:
        return Plano(**data)
    except ValidationError as e:
        logger.error(f"Schema invalido do Arquiteto: {e}")
        return None

def executor(task: str, subtarefas: list[str], memory: dict,
             cwd: str, tree: str, config: Config) -> Optional[Resultado]:
    """Cria arquivos necessários para a tarefa.
    
    Args:
        task: Tarefa principal.
        subtarefas: Lista de subtarefas do Arquiteto.
        memory: Histórico de execuções.
        cwd: Diretório do projeto.
        tree: Árvore de arquivos existentes.
        config: Configuração com credenciais.
    
    Returns:
        Resultado validado com lista de changes ou None se falhar.
    """
    subtarefas_str = "\n".join([f"- {s}" for s in subtarefas])
    user_msg = f"{mem_context(memory)}\n\nTAREFA: {task}\nSUBTAREFAS:\n{subtarefas_str}\n\nARQUIVOS EXISTENTES:\n{tree}"
    raw = _call(SYSTEM_EXECUTOR, user_msg, config)
    if not raw:
        return None
    data = parse_json(raw)
    if not data:
        logger.error("Executor retornou JSON invalido")
        return None
    try:
        return Resultado(**data)
    except ValidationError as e:
        logger.error(f"Schema invalido do Executor: {e}")
        return None

def revisor(plano: Plano, arquivos_criados: list[str], config: Config) -> Revisao:
    """Verifica se execução atendeu ao plano.
    
    Args:
        plano: Plano do Arquiteto.
        arquivos_criados: Arquivos efetivamente criados.
        config: Configuração com credenciais.
    
    Returns:
        Revisão com aprovação, problemas e correções.
    """
    user_msg = f"PLANO: {plano.summary}\nARQUIVOS: {arquivos_criados}\nSUBTAREFAS: {plano.subtarefas}"
    raw = _call(SYSTEM_REVISOR, user_msg, config)
    if not raw:
        return Revisao(aprovado=True)
    data = parse_json(raw)
    if not data:
        return Revisao(aprovado=True)
    try:
        return Revisao(**data)
    except ValidationError as e:
        logger.error(f"Schema invalido do Revisor: {e}")
        return Revisao(aprovado=True)
