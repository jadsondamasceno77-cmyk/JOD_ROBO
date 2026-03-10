"""Memória persistente com lock para acesso concorrente seguro."""
import json, os, time, logging, fcntl
from typing import Optional

logger = logging.getLogger("jod.memory")

EMPTY: dict = {"execucoes": [], "agentes_criados": [], "aprendizados": []}

def load(path: str) -> dict:
    """Carrega memória do disco com lock compartilhado.
    
    Args:
        path: Caminho do arquivo .jod_memory.json.
    
    Returns:
        Dict com histórico de execuções e aprendizados.
    """
    if not os.path.exists(path):
        return {k: list(v) for k, v in EMPTY.items()}
    try:
        with open(path, "r", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            data = json.load(f)
            fcntl.flock(f, fcntl.LOCK_UN)
            return data
    except Exception as e:
        logger.error(f"Erro ao carregar memoria: {e}")
        return {k: list(v) for k, v in EMPTY.items()}

def save(path: str, memory: dict) -> None:
    """Salva memória no disco com lock exclusivo.
    
    Args:
        path: Caminho do arquivo.
        memory: Dict com dados a salvar.
    """
    try:
        with open(path, "w", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            json.dump(memory, f, indent=2, ensure_ascii=False)
            fcntl.flock(f, fcntl.LOCK_UN)
    except Exception as e:
        logger.error(f"Erro ao salvar memoria: {e}")

def context(memory: dict) -> str:
    """Gera contexto textual das últimas execuções para o LLM.
    
    Args:
        memory: Dict com histórico.
    
    Returns:
        String formatada com histórico e aprendizados.
    """
    if not memory.get("execucoes"):
        return "Nenhuma execucao anterior."
    ctx = "HISTORICO (ultimas 5 execucoes):\n"
    for e in memory["execucoes"][-5:]:
        ctx += f"- [{e['ts']}] TAREFA: {e['task']} | RESULTADO: {e['summary']} | ARQUIVOS: {e.get('files',[])}\n"
    if memory.get("aprendizados"):
        ctx += "\nAPRENDIZADOS ACUMULADOS:\n"
        for a in memory["aprendizados"][-3:]:
            ctx += f"- {a}\n"
    return ctx

def record(memory: dict, correlation_id: str, task: str, summary: str,
           files: list, tipo: str, aprendizado: str = "") -> dict:
    """Registra execução na memória e aplica limites de retenção.
    
    Args:
        memory: Dict atual da memória.
        correlation_id: ID único da execução.
        task: Tarefa executada.
        summary: Resumo do resultado.
        files: Lista de arquivos criados.
        tipo: Tipo da tarefa (agente, site, app, etc).
        aprendizado: Lição aprendida para contexto futuro.
    
    Returns:
        Dict atualizado.
    """
    memory["execucoes"].append({
        "ts": time.strftime("%Y-%m-%d %H:%M"),
        "id": correlation_id,
        "task": task,
        "summary": summary,
        "files": files,
        "tipo": tipo
    })
    if aprendizado:
        memory["aprendizados"].append(aprendizado)
    memory["agentes_criados"].extend([f for f in files if "agents/" in f])
    memory["execucoes"] = memory["execucoes"][-50:]
    memory["aprendizados"] = memory["aprendizados"][-20:]
    return memory
