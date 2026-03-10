"""Operações de I/O seguras: escrita de arquivos e operações git."""
import os, logging, subprocess
from typing import Optional
from jod_brain.security import safe_path, validate_python, sanitize_content, SecurityError

logger = logging.getLogger("jod.io")

def write_file(base: str, user_path: str, content: str) -> bool:
    """Escreve arquivo com validação completa de segurança.
    
    Args:
        base: Diretório raiz do projeto.
        user_path: Path relativo fornecido pelo LLM.
        content: Conteúdo a escrever.
    
    Returns:
        True se escrito com sucesso, False caso contrário.
    """
    if not user_path or not content:
        logger.error("Path ou conteudo vazio")
        return False
    try:
        fp = safe_path(base, user_path)
        content = sanitize_content(content)
        if user_path.endswith(".py") and not validate_python(content, user_path):
            logger.error(f"Python invalido, nao escrito: {user_path}")
            return False
        parent = os.path.dirname(fp)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(fp, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Arquivo escrito: {user_path}")
        return True
    except SecurityError as e:
        logger.error(f"Seguranca bloqueou: {e}")
        return False
    except (IOError, OSError, PermissionError) as e:
        logger.error(f"Erro I/O em {user_path}: {e}", exc_info=True)
        return False

def git_commit_push(cwd: str, summary: str) -> bool:
    """Commit e push git sem shell=True.
    
    Args:
        cwd: Diretório do repositório.
        summary: Mensagem do commit.
    
    Returns:
        True se push feito, False se nada a commitar ou erro.
    """
    try:
        subprocess.run(["git", "add", "-A"], cwd=cwd, check=True, capture_output=True, timeout=30)
        r = subprocess.run(
            ["git", "commit", "-m", f"jod: {summary[:72]}"],
            cwd=cwd, capture_output=True, text=True, timeout=30
        )
        if "nothing to commit" in r.stdout:
            logger.info("Nada a commitar")
            return False
        subprocess.run(
            ["git", "push", "origin", "HEAD:main"],
            cwd=cwd, check=True, capture_output=True, timeout=60
        )
        logger.info("Push realizado com sucesso")
        return True
    except subprocess.TimeoutExpired:
        logger.error("Git timeout")
        return False
    except subprocess.CalledProcessError as e:
        logger.error(f"Git erro: {e.stderr}")
        return False
