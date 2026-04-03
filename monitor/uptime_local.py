#!/usr/bin/env python3
"""
X-Mom v5.0 — Monitor de Serviços Local
Monitora 7 serviços systemd a cada 60s.
Loga em /home/jod_robo/logs/uptime.jsonl
Alerta via Telegram quando serviço cai ou se recupera.
"""
import asyncio, json, os, subprocess, time, sys, logging
from pathlib import Path
from datetime import datetime, timezone

# ── Paths & Config ───────────────────────────────────────────────────────────
BASE_DIR  = Path(__file__).resolve().parent.parent
LOG_FILE  = Path("/home/jod_robo/logs/uptime.jsonl")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# Load .env
_ENV = BASE_DIR / ".env"
if _ENV.exists():
    for line in _ENV.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

BOT_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID_RAW = os.getenv("TELEGRAM_CHAT_ID", "0")
try:
    CHAT_ID = int(CHAT_ID_RAW)
except ValueError:
    CHAT_ID = 0

INTERVAL    = int(os.getenv("MONITOR_INTERVAL", "60"))
TG_API      = f"https://api.telegram.org/bot{BOT_TOKEN}"

SERVICES = [
    "jod-robo-mae",
    "jod-factory",
    "n8n",
    "jod-n8n-agent",
    "jod-telegram",
    "jod-health",
    "jod-viewer",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [MONITOR] %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/home/jod_robo/logs/monitor.log"),
    ],
)
log = logging.getLogger("xmom.monitor")


# ── State tracking (prev status per service) ─────────────────────────────────
_prev_status: dict[str, str] = {}


def check_service(name: str) -> str:
    """Returns 'active', 'inactive', 'failed', or 'unknown'."""
    try:
        r = subprocess.run(
            ["systemctl", "is-active", name],
            capture_output=True, text=True, timeout=5
        )
        return r.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def write_log(entry: dict) -> None:
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


async def send_telegram(text: str) -> bool:
    if not BOT_TOKEN or CHAT_ID == 0:
        log.warning("Telegram não configurado (BOT_TOKEN ou CHAT_ID ausente) — alerta omitido")
        return False
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.post(f"{TG_API}/sendMessage",
                             json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"})
            ok = r.status_code == 200
            if not ok:
                log.warning(f"Telegram sendMessage falhou: {r.status_code} {r.text[:200]}")
            return ok
    except Exception as e:
        log.warning(f"Telegram erro: {e}")
        return False


async def run_check() -> dict:
    ts = datetime.now(timezone.utc).isoformat()
    statuses = {svc: check_service(svc) for svc in SERVICES}
    active   = sum(1 for v in statuses.values() if v == "active")

    entry = {
        "ts":       ts,
        "services": statuses,
        "active":   active,
        "total":    len(SERVICES),
    }
    write_log(entry)
    log.info(f"check: {active}/{len(SERVICES)} active")

    # Alert on state changes
    alerts = []
    for svc, status in statuses.items():
        prev = _prev_status.get(svc, "active")  # assume active on first run
        if prev == "active" and status != "active":
            alerts.append(f"🔴 *{svc}* caiu! Status: `{status}`")
            log.warning(f"ALERTA: {svc} → {status}")
        elif prev != "active" and status == "active":
            alerts.append(f"🟢 *{svc}* se recuperou! Status: `active`")
            log.info(f"RECUPERADO: {svc} → active")
        _prev_status[svc] = status

    if alerts:
        msg = (f"⚡ *X-Mom Monitor*\n"
               f"`{ts[:19]}`\n\n"
               + "\n".join(alerts)
               + f"\n\n📊 {active}/{len(SERVICES)} serviços ativos")
        await send_telegram(msg)

    return entry


async def main():
    log.info(f"X-Mom Monitor iniciado — {len(SERVICES)} serviços, intervalo {INTERVAL}s")
    log.info(f"Telegram: {'configurado' if BOT_TOKEN and CHAT_ID else 'NÃO configurado'}")

    # Initialize prev_status silently on first check
    for svc in SERVICES:
        _prev_status[svc] = check_service(svc)
    log.info(f"Estado inicial: {_prev_status}")

    while True:
        try:
            await run_check()
        except Exception as e:
            log.error(f"Erro no ciclo de check: {e}")
        await asyncio.sleep(INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
