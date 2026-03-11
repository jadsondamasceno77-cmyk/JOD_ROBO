"""JOD_ROBO Brain v3 — Fluxo com aprovação humana antes de executar."""
import sys, os, subprocess, time, logging
from pathlib import Path
from logging.handlers import RotatingFileHandler

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from jod_brain.agents import arquiteto, executor, revisor, Config
from jod_brain.io import write_file, git_commit_push
from jod_brain import memory as mem

def setup_logging() -> None:
    fmt = '{"time":"%(asctime)s","level":"%(levelname)s","service":"jod_brain","msg":"%(message)s"}'
    handlers = [
        logging.StreamHandler(),
        RotatingFileHandler(PROJECT_ROOT / "jod_brain.log", maxBytes=10*1024*1024, backupCount=3)
    ]
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=handlers)

setup_logging()
logger = logging.getLogger("jod_brain")

class ConfigurationError(RuntimeError):
    pass

def health_check(api_key: str, cwd: str) -> None:
    if not api_key:
        raise ConfigurationError("GROQ_API_KEY nao configurada")
    r = subprocess.run(["git", "rev-parse", "--git-dir"], capture_output=True, cwd=cwd)
    if r.returncode != 0:
        raise ConfigurationError(f"{cwd} nao e repositorio git")

def get_tree(cwd: str) -> str:
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

def pedir_aprovacao(plano) -> bool:
    """Mostra plano ao usuário e aguarda aprovação explícita."""
    print("\n" + "="*60)
    print("📋 PLANO DO ARQUITETO")
    print("="*60)
    print(f"Resumo  : {plano.summary}")
    print(f"Tipo    : {plano.tipo}")
    print("\nSubtarefas:")
    for i, s in enumerate(plano.subtarefas, 1):
        print(f"  {i}. {s}")
    if plano.aprendizado:
        print(f"\nAprendizado: {plano.aprendizado}")
    print("="*60)
    while True:
        resp = input("\n✅ Aprovar e executar? [sim/nao]: ").strip().lower()
        if resp in ("sim", "s", "yes", "y"):
            return True
        if resp in ("nao", "nao", "n", "no"):
            return False
        print("Digite 'sim' ou 'nao'")

def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python jod_brain_main.py \"sua tarefa aqui\"")
        print("Exemplo: python jod_brain_main.py \"cria agente de monitoramento de precos\"")
        sys.exit(1)

    task = sys.argv[1]
    cwd = os.getcwd()
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

    # FASE 1 — ARQUITETO PLANEJA
    print("\n🧠 Arquiteto analisando tarefa...")
    plano = arquiteto(task, memory, cwd, config)
    if not plano:
        print("❌ Arquiteto falhou — verifique GROQ_API_KEY e conexão")
        sys.exit(1)

    # FASE 2 — VOCÊ APROVA OU REJEITA
    aprovado = pedir_aprovacao(plano)
    if not aprovado:
        print("\n⛔ Execução cancelada por você.")
        logger.info(f"Cancelado pelo usuario ID={correlation_id}")
        sys.exit(0)

    # FASE 3 — EXECUTOR AGE SOZINHO
    print("\n⚡ Executor criando arquivos...")
    tree = get_tree(cwd)
    resultado = executor(task, plano.subtarefas, memory, cwd, tree, config)
    if not resultado:
        print("❌ Executor falhou")
        sys.exit(1)

    arquivos_criados = []
    for c in resultado.changes:
        ok = write_file(cwd, c.file, c.content)
        if ok:
            print(f"  ✓ {c.file}")
            arquivos_criados.append(c.file)
        else:
            print(f"  ✗ bloqueado: {c.file}")

    # FASE 4 — REVISOR VERIFICA
    print("\n🔍 Revisor verificando qualidade...")
    rev = revisor(plano, arquivos_criados, config)
    if not rev.aprovado and rev.correcoes:
        print("🔧 Revisor aplicando correções automáticas...")
        for c in rev.correcoes:
            ok = write_file(cwd, c.file, c.content)
            if ok:
                print(f"  ✓ corrigido: {c.file}")
                arquivos_criados.append(c.file)
    if rev.problemas:
        print(f"⚠️  Problemas detectados: {rev.problemas}")

    # FASE 5 — MEMÓRIA APRENDE
    memory = mem.record(
        memory, correlation_id, task,
        resultado.summary, arquivos_criados,
        plano.tipo, plano.aprendizado or ""
    )
    mem.save(memory_file, memory)
    logger.info(f"Memoria atualizada — total execucoes: {len(memory['execucoes'])}")

    # FASE 6 — GIT PUSH AUTOMÁTICO
    try:
        pushed = git_commit_push(cwd, resultado.summary)
        if pushed:
            print("\n📤 Push feito no GitHub!")
    except Exception as e:
        logger.error(f"Git falhou: {e}")

    # RESULTADO FINAL
    print("\n" + "="*60)
    print("✅ CONCLUÍDO")
    print("="*60)
    print(f"ID        : {correlation_id}")
    print(f"Resumo    : {resultado.summary}")
    print(f"Arquivos  : {arquivos_criados}")
    print(f"Memória   : {len(memory['execucoes'])} execuções registradas")
    print("="*60)

if __name__ == "__main__":
    main()
