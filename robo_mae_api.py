#!/usr/bin/env python3
import os,sys
from pathlib import Path
from fastapi import FastAPI,HTTPException,Header
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import uvicorn
sys.path.insert(0,str(Path(__file__).resolve().parent))
from robo_mae import process,SQUADS
app=FastAPI(title="ELI API",version="2.0")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])
class ChatRequest(BaseModel):
    message:str
    session_id:str="default"
from collections import defaultdict
import time as _time
_rate_store=defaultdict(list)
def _rate_check(sid):
    now=_time.time();calls=[t for t in _rate_store[sid] if now-t<60];_rate_store[sid]=calls
    if len(calls)>=20:raise HTTPException(status_code=429,detail='Rate limit: 20 req/min')
    _rate_store[sid].append(now)
def _check(token):
    if token!=os.getenv("JOD_TRUST_MANIFEST","jod_robo_trust_2026_secure"):
        raise HTTPException(status_code=401,detail="Token invalido")
@app.get("/health")
async def health():
    import os
    db_url = os.getenv("DATABASE_URL","")
    total = 0
    if db_url:
        try:
            import asyncpg, asyncio
            async def _count():
                conn = await asyncpg.connect(db_url)
                r = await conn.fetchval("SELECT COUNT(*) FROM agents WHERE status=$1","active")
                await conn.close()
                return r or 0
            total = asyncio.get_event_loop().run_until_complete(_count())
        except Exception:
            total = len(SQUADS) * 12
    else:
        import sqlite3, pathlib
        db = pathlib.Path(__file__).resolve().parent / "jod_robo.db"
        try:
            conn = sqlite3.connect(str(db))
            total = conn.execute("SELECT COUNT(*) FROM agents WHERE status='active'").fetchone()[0]
            conn.close()
        except Exception:
            total = len(SQUADS) * 12
    return{"status":"ok","version":"2.0","squads":len(SQUADS),"agentes":total}
@app.post("/chat")
async def chat(req:ChatRequest,x_jod_token:Optional[str]=Header(None)):
    _check(x_jod_token)
    _rate_check(req.session_id)
    r=await process(req.message,req.session_id)
    return{"squad":r["squad"],"chief":r["chief"],"response":r["response"],"session_id":req.session_id,"score":7}
@app.get("/squads")
async def squads():
    return[{"id":k,"chief":v["chief"]}for k,v in SQUADS.items()]
@app.get("/",response_class=HTMLResponse)
async def ui():
    return open(Path(__file__).resolve().parent/"ui.html",encoding="utf-8").read() if (Path(__file__).resolve().parent/"ui.html").exists() else "<h1>X-Mom v5.0</h1><p>ui.html não encontrado</p>"


import subprocess as _sp
from datetime import datetime as _dt
import httpx as _hx

class _HR(BaseModel):
    workflow_id:str; error_log:str; broken_node_name:str
class _BR(BaseModel):
    workflow_id:str; workflow_name:str; workflow_json:dict
class _RR(BaseModel):
    workflow_id:str

_VAULT=os.path.join(os.path.dirname(__file__),"n8n_vault","workflows")
_N8N=os.getenv("N8N_URL","http://localhost:5678")
_NK=os.getenv("N8N_API_KEY","")

@app.post("/self-healing")
async def self_healing(r:_HR,x_jod_token:Optional[str]=Header(None)):
    _check(x_jod_token)
    from groq import Groq as _G
    _c=_G(api_key=os.getenv("GROQ_API_KEY",""))
    try:
        _r=_c.chat.completions.create(model="llama-3.3-70b-versatile",
            messages=[{"role":"user","content":f"Engenheiro n8n sênior. Retorne APENAS JSON: {{node_name,fix_type,new_value,reason}}\nErro: {r.error_log[:500]}\nNó: {r.broken_node_name}"}],
            temperature=0.1,max_tokens=200)
        raw=_r.choices[0].message.content.strip()
        for f in ["```json","```"]: raw=raw.removeprefix(f).removesuffix(f).strip()
        patch=json.loads(raw)
    except Exception as e:
        patch={"node_name":r.broken_node_name,"fix_type":"manual","reason":str(e)}
    lp=Path(__file__).resolve().parent/"memory"/"conversations.jsonl"
    with open(lp,"a") as lf: lf.write(json.dumps({"event":"self_healing","wf":r.workflow_id,"patch":patch},ensure_ascii=False)+"\n")
    return{"status":"patch_generated","patch":patch}

@app.post("/vault/backup")
async def vault_backup(r:_BR,x_jod_token:Optional[str]=Header(None)):
    _check(x_jod_token)
    os.makedirs(_VAULT,exist_ok=True)
    fp=os.path.join(_VAULT,f"{r.workflow_id}.json")
    with open(fp,"w") as f: json.dump(r.workflow_json,f,indent=2)
    vr=str(Path(_VAULT).parent)
    _sp.run(["git","add","."],cwd=vr,capture_output=True)
    ts=_dt.now().strftime("%Y-%m-%d %H:%M:%S")
    _sp.run(["git","commit","-m",f"BACKUP:{r.workflow_name}|{r.workflow_id}|{ts}"],cwd=vr,capture_output=True)
    return{"status":"vaulted","path":fp,"timestamp":ts}

@app.post("/vault/rollback")
async def vault_rollback(r:_RR,x_jod_token:Optional[str]=Header(None)):
    _check(x_jod_token)
    vr=str(Path(_VAULT).parent)
    fp=os.path.join(_VAULT,f"{r.workflow_id}.json")
    try:
        _sp.run(["git","checkout","HEAD~1","--",f"workflows/{r.workflow_id}.json"],cwd=vr,check=True,capture_output=True)
        with open(fp) as f: restored=json.load(f)
        async with _hx.AsyncClient(timeout=10.0) as c:
            res=await c.put(f"{_N8N}/api/v1/workflows/{r.workflow_id}",json=restored,headers={"X-N8N-API-KEY":_NK})
        _sp.run(["git","add","."],cwd=vr,capture_output=True)
        _sp.run(["git","commit","-m",f"ROLLBACK:{r.workflow_id}"],cwd=vr,capture_output=True)
        return{"status":"restored","n8n_status":res.status_code}
    except Exception as e:
        return{"status":"error","detail":str(e)}

class _AgentOSRequest(BaseModel):
    task: str
    session_id: str = "default"

class _SocialRequest(BaseModel):
    task: str
    session_id: str = "social-default"

class _BrandItem(BaseModel):
    niche: str
    audience: str

class _BrandsRequest(BaseModel):
    brands: List[_BrandItem]
    max_concurrent: int = 10

@app.post("/social")
async def social_endpoint(r: _SocialRequest, x_jod_token: Optional[str] = Header(None)):
    _check(x_jod_token)
    from social_agent import run_social_agent
    result = await run_social_agent(r.task, session_id=r.session_id)
    return {"session_id": r.session_id, **result}

@app.post("/social/brands")
async def create_brands(r: _BrandsRequest, x_jod_token: Optional[str] = Header(None)):
    _check(x_jod_token)
    from brand_pipeline import create_brands_from_list
    result = await create_brands_from_list(
        [b.model_dump() for b in r.brands],
        max_concurrent=r.max_concurrent
    )
    return result

@app.get("/social/stats")
async def social_stats(x_jod_token: Optional[str] = Header(None)):
    _check(x_jod_token)
    from brand_pipeline import get_pipeline_stats
    return await get_pipeline_stats()

@app.get("/social/brand/{brand_id}")
async def get_brand_info(brand_id: int, x_jod_token: Optional[str] = Header(None)):
    _check(x_jod_token)
    from brand_db import get_brand
    return await get_brand(brand_id) or {"error": "não encontrado"}

class _QueueBrandRequest(BaseModel):
    niche: str
    audience: str
    country: str = "BR"
    extra: dict = {}

@app.post("/social/queue")
async def queue_brand(r: _QueueBrandRequest, x_jod_token: Optional[str] = Header(None)):
    _check(x_jod_token)
    from brand_scheduler import enqueue_brand
    from geo_config import get_country, get_culture_prompt
    geo = get_country(r.country)
    extra = {**r.extra, "country": r.country, "language": geo["gtts_lang"],
             "timezone": geo["fuso"], "culture": geo["cultura"],
             "top_platforms": geo["plataformas_top"]}
    brand_id = await enqueue_brand(r.niche, r.audience, extra)
    return {"status": "queued", "brand_id": brand_id, "country": geo["nome"],
            "idioma": geo["idioma"], "plataformas": geo["plataformas_top"][:3],
            "message": f"Marca em {geo['nome']} adicionada à fila."}

@app.get("/social/countries")
async def list_countries_endpoint(x_jod_token: Optional[str] = Header(None)):
    _check(x_jod_token)
    from geo_config import list_countries
    return {"countries": list_countries(), "total": len(list_countries())}

@app.get("/social/scheduler")
async def scheduler_status(x_jod_token: Optional[str] = Header(None)):
    _check(x_jod_token)
    from brand_scheduler import get_scheduler_status
    return await get_scheduler_status()

@app.post("/social/scheduler/start")
async def scheduler_start(interval_minutes: int = 30, x_jod_token: Optional[str] = Header(None)):
    _check(x_jod_token)
    from brand_scheduler import start_scheduler
    start_scheduler(interval_minutes)
    return {"status": "started", "interval_minutes": interval_minutes}

class _MediaRequest(BaseModel):
    brand_id: int
    brand_name: str
    roteiro: str
    legenda: str

@app.post("/social/media")
async def gerar_midia(r: _MediaRequest, x_jod_token: Optional[str] = Header(None)):
    _check(x_jod_token)
    from media_generator import gerar_pack_midia
    return await gerar_pack_midia(r.brand_id, r.brand_name, r.roteiro, r.legenda)

@app.post("/social/scheduler/stop")
async def scheduler_stop(x_jod_token: Optional[str] = Header(None)):
    _check(x_jod_token)
    from brand_scheduler import stop_scheduler
    stop_scheduler()
    return {"status": "stopped"}


@app.get("/status")
async def get_status():
    import httpx
    services = {}
    checks = [
        ("n8n", "http://localhost:5678/healthz"),
        ("agente_motor", "http://localhost:37780/health"),
    ]
    async with httpx.AsyncClient(timeout=2.0) as c:
        for name, url in checks:
            try:
                r = await c.get(url)
                services[name] = r.status_code < 400
            except:
                services[name] = False
    return {"services": services}
@app.on_event("startup")
async def startup_scheduler():
    from brand_db import init_db
    from brand_scheduler import start_scheduler
    await init_db()
    start_scheduler(interval_minutes=30)

@app.post("/agent-os")
async def agent_os_endpoint(r: _AgentOSRequest, x_jod_token: Optional[str] = Header(None)):
    _check(x_jod_token)
    from agent_os import run_agent_os
    result = await run_agent_os(r.task, session_id=r.session_id)
    return {"session_id": r.session_id, **result}


# ─── Social Playwright endpoints ──────────────────────────────────────────────

class _CreateProfileRequest(BaseModel):
    brand_id: int
    brand_name: str
    niche: str
    email_base: str
    password: str
    platforms: List[str] = ["instagram", "tiktok", "twitter", "linkedin", "youtube"]

class _PostRequest(BaseModel):
    brand_id: int
    platform: str
    caption: str = ""
    hashtags: List[str] = []
    media_path: str = ""
    type: str = "feed"  # feed | story | reel

class _CommentRequest(BaseModel):
    brand_id: int
    platform: str
    brand_context: str = ""
    max_comments: int = 10

@app.post("/social/create-profile")
async def create_profile_endpoint(r: _CreateProfileRequest, x_jod_token: Optional[str] = Header(None)):
    _check(x_jod_token)
    from social_playwright import create_profile
    result = await create_profile(
        r.brand_id, r.brand_name, r.niche, r.email_base, r.password, r.platforms
    )
    return {"brand_id": r.brand_id, "results": result}

@app.post("/social/post")
async def auto_post_endpoint(r: _PostRequest, x_jod_token: Optional[str] = Header(None)):
    _check(x_jod_token)
    from social_playwright import auto_post
    content = {
        "caption": r.caption,
        "hashtags": r.hashtags,
        "media_path": r.media_path,
        "type": r.type,
    }
    result = await auto_post(r.brand_id, r.platform, content)
    return {"brand_id": r.brand_id, "platform": r.platform, **result}

@app.post("/social/respond-comments")
async def respond_comments_endpoint(r: _CommentRequest, x_jod_token: Optional[str] = Header(None)):
    _check(x_jod_token)
    from social_playwright import respond_comments
    result = await respond_comments(r.brand_id, r.platform, r.brand_context, r.max_comments)
    return {"brand_id": r.brand_id, **result}

@app.get("/dashboard",response_class=HTMLResponse)
async def dashboard():
    p=Path(__file__).resolve().parent/"dashboard.html"
    return p.read_text(encoding="utf-8") if p.exists() else "<h1>404</h1>"

if __name__=="__main__":
    uvicorn.run(app,host="0.0.0.0",port=37779)
