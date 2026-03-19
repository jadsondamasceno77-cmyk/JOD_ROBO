import asyncio
import logging
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
API_TOKEN = os.getenv("JOD_ROBO_API_TOKEN", "dev-token")
ALLOWED_USER_ID = int(os.environ["TELEGRAM_ALLOWED_USER_ID"])
ROBO_URL = "http://127.0.0.1:37777"
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


async def tg_call(client: httpx.AsyncClient, method: str, **payload) -> dict:
    r = await client.post(f"{TG_API}/{method}", json=payload, timeout=35)
    r.raise_for_status()
    return r.json()


async def send_message(client: httpx.AsyncClient, chat_id: int, text: str) -> None:
    await tg_call(client, "sendMessage", chat_id=chat_id, text=text, parse_mode="Markdown")


def format_orchestrate(data: dict) -> str:
    ao = data.get("analyst_output", {})
    eo = data.get("executor_output", {})

    beneficios = ao.get("principais_benefícios") or ao.get("principais_beneficios") or []
    acoes = eo.get("acoes_recomendadas") or []

    lines = [
        f"*Analista — {ao.get('tema', '')}*",
        f"Posição: {ao.get('posicao', '')}",
        f"Descrição: {ao.get('descrição') or ao.get('descricao', '')}",
    ]
    if beneficios:
        lines.append("Benefícios:")
        for b in beneficios:
            lines.append(f"  • {b}")
    if ao.get("exemplo_de_uso"):
        lines.append(f"Exemplo: {ao['exemplo_de_uso']}")

    lines += [
        "",
        f"*Executor — {eo.get('tema', '')}*",
        f"Posição: {eo.get('posicao', '')}",
        f"Descrição: {eo.get('descrição') or eo.get('descricao', '')}",
    ]
    if acoes:
        lines.append("Ações recomendadas:")
        for a in acoes:
            lines.append(f"  • {a}")
    lines.append(f"Próximo passo: {eo.get('proximo_passo', '')}")

    return "\n".join(lines)


async def handle_update(client: httpx.AsyncClient, update: dict) -> None:
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return

    chat_id: int = msg["chat"]["id"]
    user_id: int = msg["from"]["id"]
    text: str = msg.get("text", "").strip()

    if user_id != ALLOWED_USER_ID:
        await send_message(client, chat_id, "Acesso negado.")
        return

    if text == "/start":
        await send_message(client, chat_id,
            "JOD ROBO online.\nEnvie qualquer mensagem para orquestrar.\n/help para comandos.")
        return

    if text == "/help":
        await send_message(client, chat_id,
            "*Comandos disponíveis*\n"
            "/start — inicia o bot\n"
            "/status — verifica se o servidor está online\n"
            "/help — esta mensagem\n\n"
            "Qualquer outro texto é enviado ao /orchestrate.")
        return

    if text == "/status":
        try:
            r = await client.get(f"{ROBO_URL}/health/live", timeout=5)
            data = r.json()
            await send_message(client, chat_id,
                f"Servidor: *online*\nts: {data.get('ts', '?')}")
        except Exception as exc:
            await send_message(client, chat_id, f"Servidor: *offline*\n`{exc}`")
        return

    if not text or text.startswith("/"):
        await send_message(client, chat_id, "Comando não reconhecido. Use /help.")
        return

    await send_message(client, chat_id, "_Processando…_")
    if text.startswith("/analise "):
        prompt = text[len("/analise "):]
        try:
            r = await client.post(
                f"{ROBO_URL}/orchestrate",
                json={"prompt": prompt},
                headers={"Authorization": f"Bearer {API_TOKEN}"},
                timeout=120,
            )
            if r.status_code != 200:
                await send_message(client, chat_id,
                    f"Erro do servidor: `{r.status_code}`\n```{r.text[:800]}```")
                return
            reply = format_orchestrate(r.json())
            await send_message(client, chat_id, reply)
        except Exception as exc:
            log.exception("orchestrate error")
            await send_message(client, chat_id, f"Erro ao chamar /orchestrate:\n`{exc}`")
    else:
        try:
            r = await client.post(
                f"{ROBO_URL}/chat",
                json={"prompt": text},
                headers={"Authorization": f"Bearer {API_TOKEN}"},
                timeout=120,
            )
            if r.status_code != 200:
                await send_message(client, chat_id,
                    f"Erro do servidor: `{r.status_code}`\n```{r.text[:800]}```")
                return
            await send_message(client, chat_id, r.json()["response"])
        except Exception as exc:
            log.exception("chat error")
            await send_message(client, chat_id, f"Erro ao chamar /chat:\n`{exc}`")


async def poll() -> None:
    offset = 0
    log.info("Bot iniciado — long polling")
    async with httpx.AsyncClient() as client:
        while True:
            try:
                resp = await client.get(
                    f"{TG_API}/getUpdates",
                    params={"offset": offset, "timeout": 30, "allowed_updates": '["message"]'},
                    timeout=40,
                )
                data = resp.json()
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    asyncio.create_task(handle_update(client, update))
            except (httpx.RequestError, httpx.TimeoutException) as exc:
                log.warning("getUpdates error: %s — retrying in 5s", exc)
                await asyncio.sleep(5)
            except Exception:
                log.exception("getUpdates unexpected error — retrying in 5s")
                await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(poll())
