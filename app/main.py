import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.agent import agent

app = FastAPI(title="JOD_ROBO", version="2.0")

class Msg(BaseModel):
    text: str
    context: Optional[str] = None

class Code(BaseModel):
    code: str

class Url(BaseModel):
    url: str

class Clone(BaseModel):
    name: str
    role: str
    system_prompt: str

@app.get("/")
async def root(): return {"status": "online", "agent": agent.name}

@app.get("/health")
@app.get("/healthz")
async def health(): return {"status": "online", "agent": agent.name}

@app.post("/chat")
async def chat(m: Msg):
    try: return {"reply": await agent.think(m.text, m.context)}
    except Exception as e: raise HTTPException(500, str(e))

@app.post("/intent")
async def intent(data: dict):
    try:
        text = data.get("text", data.get("message", str(data)))
        return {"status": "ok", "reply": await agent.think(text)}
    except Exception as e: return {"status": "error", "error": str(e)}

@app.post("/exec")
async def exc(r: Code):
    try: return await agent.execute_python(r.code)
    except Exception as e: raise HTTPException(500, str(e))

@app.post("/analyze")
async def analyze(r: Url):
    try: return {"report": await agent.analyze_site(r.url)}
    except Exception as e: raise HTTPException(500, str(e))

@app.post("/clone")
async def clone(r: Clone):
    try:
        c = agent.clone(r.name, r.role, r.system_prompt)
        return {"status": "cloned", "name": c.name, "role": c.role}
    except Exception as e: raise HTTPException(500, str(e))
