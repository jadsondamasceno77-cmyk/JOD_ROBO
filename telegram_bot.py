#!/usr/bin/env python3
import os,sys,asyncio,logging
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent/".env")
from telegram import Update
from telegram.ext import ApplicationBuilder,CommandHandler,MessageHandler,ContextTypes,filters
from telegram.constants import ParseMode
sys.path.insert(0,str(Path(__file__).resolve().parent))
from robo_mae import process,SQUADS
logging.basicConfig(level=logging.INFO)
TOKEN=os.getenv("TELEGRAM_BOT_TOKEN","")
MODE={}
def get_mode(cid): return MODE.get(cid,"eli")
async def cmd_start(u,c):
    await u.message.reply_text("⚡ *JOD\_ROBO ativo*\n\n/eli — modo ELI\n/mae — modo Robô\-mãe\n/status — serviços\n/squads — lista squads\n\nDigite sua mensagem\.",parse_mode=ParseMode.MARKDOWN_V2)
async def cmd_eli(u,c):
    MODE[u.effective_chat.id]="eli"
    await u.message.reply_text("⚡ Modo *ELI* ativado\.",parse_mode=ParseMode.MARKDOWN_V2)
async def cmd_mae(u,c):
    MODE[u.effective_chat.id]="mae"
    await u.message.reply_text("🤖 Modo *ROBÔ\-MÃE* ativado\.",parse_mode=ParseMode.MARKDOWN_V2)
async def cmd_status(u,c):
    import httpx
    svcs=[("Factory","http://localhost:37777/health"),("ELI API","http://localhost:37779/health"),("N8N","http://localhost:5678/healthz")]
    lines=[]
    async with httpx.AsyncClient(timeout=4.0) as cl:
        for n,url in svcs:
            try: await cl.get(url); lines.append(f"✅ {n}")
            except: lines.append(f"❌ {n}")
    await u.message.reply_text("\n".join(lines))
async def cmd_squads(u,c):
    await u.message.reply_text("\n".join([f"• {k}" for k in SQUADS]))
async def on_message(u,c):
    msg=u.message.text.strip()
    cid=u.effective_chat.id
    mode=get_mode(cid)
    session=f"tg-{cid}"
    await u.message.chat.send_action("typing")
    try:
        force="c-level-squad" if mode=="mae" else None
        r=await process(msg,session,force)
        if r.get("response"): r["response"] = await executar_n8n(r["response"], session) if any(w in r["response"].lower() for w in ["criar","executar","listar","ativar","workflow","n8n"]) else r["response"]
        sq=r.get("squad","?"); ch=r.get("chief","?"); resp=r.get("response","")
        prefix="🤖 ROBÔ-MÃE" if mode=="mae" else "⚡ ELI"
        reply=f"{prefix} [{sq} → {ch}]\n\n{resp}"
        if len(reply)>4000: reply=reply[:3990]+"\n\n[truncado]"
        await u.message.reply_text(reply)
    except Exception as e:
        await u.message.reply_text(f"❌ Erro: {str(e)[:200]}")
def main():
    if not TOKEN: print("❌ TELEGRAM_BOT_TOKEN ausente"); return
    app=ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",cmd_start))
    app.add_handler(CommandHandler("eli",cmd_eli))
    app.add_handler(CommandHandler("mae",cmd_mae))
    app.add_handler(CommandHandler("status",cmd_status))
    app.add_handler(CommandHandler("squads",cmd_squads))
    app.add_handler(MessageHandler(filters.TEXT&~filters.COMMAND,on_message))
    print("⚡ Bot Telegram JOD_ROBO iniciado — @jodrobo_bot")
    app.run_polling(drop_pending_updates=True)
if __name__=="__main__": main()
import httpx, asyncio

async def executar_n8n(task: str, session_id: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post("http://localhost:37780/execute", json={
                "task": task,
                "session_id": session_id,
                "channel": "telegram"
            })
            data = r.json()
            return data.get("summary", str(data))
    except Exception as e:
        return f"Erro n8n: {e}"
