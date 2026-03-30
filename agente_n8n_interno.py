#!/usr/bin/env python3
import os,json,asyncio
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent/".env")
import httpx

N8N_URL=os.getenv("N8N_URL","http://localhost:5678")
N8N_KEY=os.getenv("N8N_API_KEY","")
HEADERS={"X-N8N-API-KEY":N8N_KEY,"Content-Type":"application/json"}

TEMPLATES={
    "webhook_email":{"name":"Webhook → Email","nodes":[{"id":"1","name":"Webhook","type":"n8n-nodes-base.webhook","typeVersion":1,"position":[250,300],"parameters":{"path":"jod-hook","responseMode":"onReceived"}},{"id":"2","name":"Send Email","type":"n8n-nodes-base.emailSend","typeVersion":2,"position":[500,300],"parameters":{"toEmail":"={{$json.email}}","subject":"JOD_ROBO Alert","text":"={{$json.message}}"}}],"connections":{"Webhook":{"main":[[{"node":"Send Email","type":"main","index":0}]]}}},
    "schedule_http":{"name":"Schedule → HTTP","nodes":[{"id":"1","name":"Schedule Trigger","type":"n8n-nodes-base.scheduleTrigger","typeVersion":1,"position":[250,300],"parameters":{"rule":{"interval":[{"field":"hours","minutesInterval":1}]}}},{"id":"2","name":"HTTP Request","type":"n8n-nodes-base.httpRequest","typeVersion":4,"position":[500,300],"parameters":{"url":"http://localhost:37779/health","method":"GET"}}],"connections":{"Schedule Trigger":{"main":[[{"node":"HTTP Request","type":"main","index":0}]]}}},
    "webhook_code":{"name":"Webhook → Code","nodes":[{"id":"1","name":"Webhook","type":"n8n-nodes-base.webhook","typeVersion":1,"position":[250,300],"parameters":{"path":"jod-process","responseMode":"lastNode"}},{"id":"2","name":"Code","type":"n8n-nodes-base.code","typeVersion":2,"position":[500,300],"parameters":{"jsCode":"const input=$input.all();\nreturn input.map(i=>({json:{processed:true,data:i.json,ts:new Date().toISOString()}}));"}}],"connections":{"Webhook":{"main":[[{"node":"Code","type":"main","index":0}]]}}},
    "eli_notifier":{"name":"ELI Notifier","nodes":[{"id":"1","name":"Webhook","type":"n8n-nodes-base.webhook","typeVersion":1,"position":[250,300],"parameters":{"path":"eli-notify","responseMode":"lastNode"}},{"id":"2","name":"HTTP ELI","type":"n8n-nodes-base.httpRequest","typeVersion":4,"position":[500,300],"parameters":{"url":"http://localhost:37779/chat","method":"POST","sendHeaders":True,"headerParameters":{"parameters":[{"name":"Content-Type","value":"application/json"},{"name":"x-jod-token","value":"jod_robo_trust_2026_secure"}]},"sendBody":True,"bodyContentType":"json","jsonBody":"{\"message\":\"={{$json.message}}\",\"session_id\":\"n8n-eli\"}"}}],"connections":{"Webhook":{"main":[[{"node":"HTTP ELI","type":"main","index":0}]]}}}
}

def _detect(desc):
    d=desc.lower()
    if any(w in d for w in ["email","notif"]): return "webhook_email"
    if any(w in d for w in ["schedule","agend","hora","cron"]): return "schedule_http"
    if any(w in d for w in ["eli","chat","robo"]): return "eli_notifier"
    return "webhook_code"

async def create_from_description(description):
    tk=_detect(description)
    tmpl=TEMPLATES[tk]
    wf={"name":f"JOD — {description[:40]}","nodes":tmpl["nodes"],"connections":tmpl["connections"],"settings":{"executionOrder":"v1"},"active":False}
    async with httpx.AsyncClient(timeout=15.0) as c:
        r=await c.post(f"{N8N_URL}/api/v1/workflows",headers=HEADERS,json=wf)
    d=r.json(); wid=d.get("id","?")
    return{"id":wid,"name":wf["name"],"template":tk,"url":f"{N8N_URL}/workflow/{wid}","status":r.status_code}

async def list_workflows():
    async with httpx.AsyncClient(timeout=10.0) as c:
        r=await c.get(f"{N8N_URL}/api/v1/workflows",headers=HEADERS)
    d=r.json(); wfs=d.get("data",d) if isinstance(d,dict) else d
    return[{"id":w["id"],"name":w["name"],"active":w.get("active",False)} for w in (wfs if isinstance(wfs,list) else [])]

async def activate_workflow(wid):
    async with httpx.AsyncClient(timeout=10.0) as c:
        r=await c.patch(f"{N8N_URL}/api/v1/workflows/{wid}",headers=HEADERS,json={"active":True})
    return{"id":wid,"status":r.status_code}

if __name__=="__main__":
    import sys
    cmd=sys.argv[1] if len(sys.argv)>1 else "list"
    if cmd=="list": r=asyncio.run(list_workflows()); [print(f"  [{w['id']}] {w['name']}") for w in r]
    elif cmd=="create": r=asyncio.run(create_from_description(" ".join(sys.argv[2:]))); print(r)
