"""JOD_ROBO Brain v3 — Fluxo com aprovação humana + loop autônomo."""
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
    print("\n" + "="*60)
    print("📋 PLANO DO ARQUITETO (JOD)")
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
        if resp in ("nao", "n", "no"):
            return False
        print("Digite sim ou nao")

def executar(task: str, cwd: str, config: Config, memory: dict,
             memory_file: str, correlation_id: str, auto_apply: bool) -> list:
    """Executa o fluxo completo: arquiteto → aprovação → executor → revisor → git."""
    plano = arquiteto(task, memory, cwd, config)
    if not plano:
        print("❌ Arquiteto falhou")
        return []

    if not auto_apply and not os.environ.get("JOD_API_MODE"):
        aprovado = pedir_aprovacao(plano)
        if not aprovado:
            print("\n⛔ Cancelado.")
            return []

    print("\n⚡ Executor criando arquivos...")
    tree = get_tree(cwd)
    resultado = executor(task, plano.subtarefas, memory, cwd, tree, config)
    if not resultado:
        print("❌ Executor falhou")
        return []

    arquivos_criados = []
    for c in resultado.changes:
        ok = write_file(cwd, c.file, c.content)
        status = "✓" if ok else "✗ bloqueado:"
        print(f"  {status} {c.file}")
        if ok:
            arquivos_criados.append(c.file)

    print("\n🔍 Revisor verificando...")
    rev = revisor(plano, arquivos_criados, config)
    if not rev.aprovado and rev.correcoes:
        print("🔧 Aplicando correções...")
        for c in rev.correcoes:
            ok = write_file(cwd, c.file, c.content)
            if ok:
                print(f"  ✓ corrigido: {c.file}")
                arquivos_criados.append(c.file)

    memory = mem.record(memory, correlation_id, task,
                        resultado.summary, arquivos_criados,
                        plano.tipo, plano.aprendizado or "")
    mem.save(memory_file, memory)

    try:
        pushed = git_commit_push(cwd, resultado.summary)
        if pushed:
            print("\n📤 Push feito!")
    except Exception as e:
        logger.error(f"Git falhou: {e}")

    print("\n" + "="*60)
    print("✅ CONCLUÍDO")
    print("="*60)
    print(f"ID      : {correlation_id}")
    print(f"Resumo  : {resultado.summary}")
    print(f"Arquivos: {arquivos_criados}")
    print(f"Memória : {len(memory['execucoes'])} execuções")
    print("="*60)
    return arquivos_criados

def autonomous_loop(cwd: str, config: Config, memory_file: str, interval: int = 300) -> None:
    """Loop autônomo: roda a cada X segundos sem precisar de comando."""
    logger.info(f"🔄 Loop autônomo iniciado — intervalo: {interval}s")
    print(f"\n🔄 JOD rodando em modo autônomo (a cada {interval//60}min)")
    print("Ctrl+C para parar\n")
    while True:
        try:
            correlation_id = f"jod_{int(time.time())}_{os.urandom(3).hex()}"
            memory = mem.load(memory_file)
            task = "verifique tarefas pendentes na memoria, identifique melhorias no projeto e aja se necessario"
            logger.info(f"Loop ID={correlation_id}")
            executar(task, cwd, config, memory, memory_file, correlation_id, auto_apply=True)
        except KeyboardInterrupt:
            print("\n⛔ Loop autônomo encerrado.")
            break
        except Exception as e:
            logger.error(f"Erro no loop: {e}", exc_info=True)
        time.sleep(interval)

def main() -> None:
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

    # Modo loop autônomo
    if "--loop" in sys.argv:
        interval = 300
        if "--interval" in sys.argv:
            idx = sys.argv.index("--interval")
            if idx + 1 < len(sys.argv):
                interval = int(sys.argv[idx + 1])
        autonomous_loop(cwd, config, memory_file, interval)
        return

    # Modo normal: precisa de tarefa
    if len(sys.argv) < 2:
        print("Uso:")
        print("  python jod_brain_main.py \"sua tarefa\"          # com aprovação")
        print("  python jod_brain_main.py \"sua tarefa\" --apply  # sem aprovação")
        print("  python jod_brain_main.py --loop                 # autônomo (5min)")
        print("  python jod_brain_main.py --loop --interval 600  # autônomo (10min)")
        sys.exit(1)

    task = sys.argv[1]
    auto_apply = "--apply" in sys.argv
    correlation_id = f"jod_{int(time.time())}_{os.urandom(3).hex()}"
    logger.info(f"ID={correlation_id} task={task[:80]}")
    memory = mem.load(memory_file)

    print("\n🧠 JOD analisando tarefa...")
    executar(task, cwd, config, memory, memory_file, correlation_id, auto_apply)

if __name__ == "__main__":
    main()
