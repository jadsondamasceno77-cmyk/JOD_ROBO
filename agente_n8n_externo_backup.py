#!/usr/bin/env python3
import os,sys
from pathlib import Path
from fastapi import FastAPI,HTTPException,Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn
sys.path.insert(0,str(Path(__file__).resolve().parent))
from agente_n8n_interno import create_from_description,list_workflows,activate_workflow

app=FastAPI(title="JOD N8N Agent",version="1.0")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])
TOKEN=os.getenv("JOD_TRUST_MANIFEST","jod_robo_trust_2026_secure")

def auth(t):
    if t!=TOKEN: raise HTTPException(status_code=401,detail="Token invalido")

class CR(BaseModel):
    description:str
    activate:bool=False

@app.get("/health")
async def health():
    wfs=await list_workflows()
    return{"status":"ok","workflows":len(wfs),"port":37780}

@app.post("/workflow/create")
async def create(req:CR,x_jod_token:Optional[str]=Header(None)):
    auth(x_jod_token)
    r=await create_from_description(req.description)
    if req.activate and r.get("id")!="?":
        await activate_workflow(r["id"]); r["activated"]=True
    return r

@app.get("/workflow/list")
async def wlist(x_jod_token:Optional[str]=Header(None)):
    auth(x_jod_token); return await list_workflows()

if __name__=="__main__":
    uvicorn.run(app,host="0.0.0.0",port=37780)
