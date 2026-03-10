"""JOD_ROBO Brain v3 — Sistema multi-agente com memória persistente."""
import sys, os, subprocess, time, logging
from pathlib import Path
from logging.handlers import RotatingFileHandler

# Path portátil — funciona em WSL, Docker, qualquer usuário
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from jod_brain.agents import arquiteto, executor, revisor, Config
from jod_brain.io import write_file, git_commit_push
from jod_brain import memory as mem

# Logging com rotação
def setup_logging() -> None:
    """Configura logging estruturado com rotação de arquivo."""
    fmt = '{"time":"%(asctime)s","level":"%(levelname)s","service":"jod_brain","msg":"%(message)s"}'
    handlers = [
        logging.StreamHandler(),
        RotatingFileHandler(PROJECT_ROOT / "jod_brain.log", maxBytes=10*1024*1024, backupCount=3)
    ]
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=handlers)

setup_logging()
logger = logging.getLogger("jod_brain")

class ConfigurationError(RuntimeError):
    """Configuração inválida ou ausente."""

def health_check(api_key: str, cwd: str) -> None:
    """Valida configuração mínima antes de executar.
    
    Args:
        api_key: Chave da API Groq.
        cwd: Diretório de trabalho do projeto.
    
    Raises:
        ConfigurationError: Se API key ausente ou diretório não for repo git.
    """
    if not api_key:
        raise ConfigurationError("GROQ_API_KEY nao configurada — export GROQ_API_KEY=sua_chave")
    result = subprocess.run(["git", "rev-parse", "--git-dir"], capture_output=True, cwd=cwd)
    if result.returncode != 0:
        raise ConfigurationError(f"Diretorio {cwd} nao e um repositorio git")

def get_tree(cwd: str) -> str:
    """Retorna árvore de arquivos do projeto excluindo artefatos.
    
    Args:
        cwd: Diretório raiz.
    
    Returns:
        String com paths dos arquivos encontrados.
    """
    try:
        return subprocess.check_output(
            ["find", ".", "-type", "f",
             "-not", "-path", "./.git/*",
             "-not", "-path", "./__pycache__/*",
             "-not", "-name", "*.pyc",
             "-not", "-name", ".jod_memory.json"],
            text=True, cwd=cwd, timeout=10
        ).strip()
    except Exception:
        return ""

def main() -> None:
    """Entry point principal do JOD_ROBO Brain."""
    if len(sys.argv) < 2:
        print("Uso: python jod_brain_main.py <tarefa> [--apply]")
        sys.exit(1)

    task = sys.argv[1]
    cwd = os.getcwd()
    auto_apply = "--apply" in sys.argv
    api_key = os.environ.get("GROQ_API_KEY", "")
    memory_file = os.path.join(cwd, ".jod_memory.json")

    try:
        health_check(api_key, cwd)
    except ConfigurationError as e:
        print(f"❌ {e}")
        sys.exit(1)

    config = Config(
        api_key=api_key,
        ollama_host=os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434"),
        ollama_model=os.environ.get("OLLAMA_MODEL", "llama3.2:1b")
    )
    correlation_id = f"jod_{int(time.time())}_{os.urandom(3).hex()}"
    logger.info(f"ID={correlation_id} task={task[:80]}")
    memory = mem.load(memory_file)

    # 1. ARQUITETO
    print("\n🧠 Arquiteto analisando tarefa...")
    plano = arquiteto(task, memory, cwd, config)
    if not plano:
        print("❌ Arquiteto falhou — verifique GROQ_API_KEY e conexão")
        sys.exit(1)

    print(f"\n📋 Plano: {plano.summary}")
    print(f"📌 Subtarefas: {plano.subtarefas}")
    print(f"🔑 ID: {correlation_id}\n")

    if not auto_apply:
        print("Use --apply para executar.")
        sys.exit(0)

    # 2. EXECUTOR
    print("⚡ Executor criando arquivos...")
    tree = get_tree(cwd)
    resultado = executor(task, plano.subtarefas, memory, cwd, tree, config)
    if not resultado:
        print("❌ Executor falhou")
        sys.exit(1)

    arquivos_criados = []
    for c in resultado.changes:
        ok = write_file(cwd, c.file, c.content)
        if ok:
            print(f"✓ {c.file}")
            arquivos_criados.append(c.file)
        else:
            print(f"✗ bloqueado: {c.file}")

    # 3. REVISOR
    print("\n🔍 Revisor verificando...")
    revisao = revisor(plano, arquivos_criados, config)
    if not revisao.aprovado and revisao.correcoes:
        print("🔧 Aplicando correcoes...")
        for c in revisao.correcoes:
            ok = write_file(cwd, c.file, c.content)
            if ok:
                print(f"✓ corrigido: {c.file}")
                arquivos_criados.append(c.file)

    # 4. MEMÓRIA
    memory = mem.record(
        memory, correlation_id, task,
        resultado.summary, arquivos_criados,
        plano.tipo, plano.aprendizado or ""
    )
    mem.save(memory_file, memory)

    # 5. GIT
    try:
        pushed = git_commit_push(cwd, resultado.summary)
        if pushed:
            print("📤 Push feito!")
    except Exception as e:
        logger.error(f"Git falhou mas execucao foi concluida: {e}")

    logger.info(f"Concluido ID={correlation_id} arquivos={arquivos_criados}")
    print(f"\n✅ Concluído! Arquivos: {arquivos_criados}")

if __name__ == "__main__":
    main()
