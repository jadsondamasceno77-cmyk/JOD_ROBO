"""Segurança: validação de paths, código Python e sanitização de conteúdo."""
import os, ast, logging
from pathlib import Path

logger = logging.getLogger("jod.security")

ALLOWED_EXTENSIONS = {".py", ".md", ".txt", ".json", ".html", ".css", ".js", ".sh", ".yaml", ".yml"}
PROTECTED_FILES = {
    "app/main.py","app/agent.py","app/logging.py",
    "requirements.txt","Dockerfile",".env.example","app/ui.html"
}

class SecurityError(ValueError):
    """Violação de segurança detectada."""

def safe_path(base: str, user_path: str) -> str:
    """Valida e retorna path absoluto seguro contra path traversal.
    
    Args:
        base: Diretório raiz permitido.
        user_path: Path fornecido pelo LLM.
    
    Returns:
        Path absoluto validado.
    
    Raises:
        SecurityError: Se path traversal, extensão proibida ou arquivo protegido.
    """
    real_base = os.path.realpath(base)
    real_target = os.path.realpath(os.path.join(base, user_path))
    if not real_target.startswith(real_base + os.sep):
        raise SecurityError(f"Path traversal bloqueado: {user_path}")
    ext = Path(user_path).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise SecurityError(f"Extensao nao permitida: {ext}")
    norm = os.path.normpath(user_path).replace("\\", "/")
    if norm in PROTECTED_FILES:
        raise SecurityError(f"Arquivo protegido: {norm}")
    return real_target

def validate_python(code: str, filename: str = "<unknown>") -> bool:
    """Valida sintaxe Python via AST antes de escrever em disco.
    
    Args:
        code: Código Python a validar.
        filename: Nome do arquivo para mensagens de erro.
    
    Returns:
        True se válido, False se inválido.
    """
    try:
        ast.parse(code)
        return True
    except SyntaxError as e:
        logger.error(f"Sintaxe invalida em {filename}: {e}")
        return False

def sanitize_content(content: str) -> str:
    """Remove BOM e caracteres de controle perigosos.
    
    Args:
        content: Conteúdo bruto do LLM.
    
    Returns:
        Conteúdo sanitizado.
    """
    return content.lstrip('\ufeff').replace('\r\n', '\n').replace('\r', '\n')
