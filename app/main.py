import os
import logging
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from typing import Optional
from app.agent import agent
from app.logging import logger

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

@app.exception_handler(Exception)
async def catch_all_exceptions(request: Request, exc: Exception):
    logger.error(f"Request: {request.method} {request.url.path} - Error: {str(exc)}")
    return JSONResponse(content={"status": "error", "error": str(exc)}, status_code=500)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Request: {request.method} {request.url.path} - Validation Error: {str(exc)}")
    return JSONResponse(content={"status": "error", "error": str(exc)}, status_code=422)

@app.get("/")
async def root():
    logger.info("Request: /")
    return {"status": "online", "agent": agent.name}

@app.get("/health")
@app.get("/healthz")
async def health():
    logger.info("Request: /health")
    return {"status": "online", "agent": agent.name}

@app.post("/chat")
async def chat(m: Msg):
    try:
        logger.info(f"Request: /chat - Text: {m.text}")
        return {"reply": await agent.think(m.text, m.context)}
    except Exception as e:
        logger.error(f"Request: /chat - Error: {str(e)}")
        raise HTTPException(500, str(e))

@app.post("/intent")
async def intent(data: dict):
    try:
        logger.info(f"Request: /intent - Data: {data}")
        text = data.get("text", data.get("message", str(data)))
        return {"status": "ok", "reply": await agent.think(text)}
    except Exception as e:
        logger.error(f"Request: /intent - Error: {str(e)}")
        return {"status": "error", "error": str(e)}

@app.post("/exec")
async def exc(r: Code):
    try:
        logger.info(f"Request: /exec - Code: {r.code}")
        return await agent.execute_python(r.code)
    except Exception as e:
        logger.error(f"Request: /exec - Error: {str(e)}")
        raise HTTPException(500, str(e))

@app.post("/analyze")
async def analyze(r: Url):
    try:
        logger.info(f"Request: /analyze - URL: {r.url}")
        return {"report": await agent.analyze_site(r.url)}
    except Exception as e:
        logger.error(f"Request: /analyze - Error: {str(e)}")
        raise HTTPException(500, str(e))

@app.post("/clone")
async def clone(r: Clone):
    try:
        logger.info(f"Request: /clone - Name: {r.name}")
        c = agent.clone(r.name, r.role, r.system_prompt)
        return {"status": "cloned", "name": c.name, "role": c.role}
    except Exception as e:
        logger.error(f"Request: /clone - Error: {str(e)}")
        raise HTTPException(500, str(e))