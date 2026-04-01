import os as _os
from groq import Groq as _Groq
import json as _json
_groq_client = _Groq(api_key=_os.getenv("GROQ_API_KEY",""))

#!/usr/bin/env python3
"""
JOD_ROBO — Agente N8N v2.0
Executor real: cria, lista, ativa e deleta workflows no n8n via API REST.
Faixa preta: todos os 6 pilares do n8n Expert.
Compatível com n8n v2.x
"""

import asyncio, json, os
import httpx
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

N8N_URL = os.getenv("N8N_URL", "http://localhost:5678")
N8N_KEY = os.getenv("N8N_API_KEY", "")
HEADERS = {"X-N8N-API-KEY": N8N_KEY, "Content-Type": "application/json"}

# ─── API CALLS ──────────────────────────────────────────────────────────────────

async def n8n_get(path):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{N8N_URL}/api/v1{path}", headers=HEADERS)
        r.raise_for_status()
        return r.json()

async def n8n_post(path, payload):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(f"{N8N_URL}/api/v1{path}", headers=HEADERS, json=payload)
        if not r.is_success:
            raise Exception(f"n8n API error {r.status_code}: {r.text}")
        return r.json()

async def n8n_put(path, payload):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.put(f"{N8N_URL}/api/v1{path}", headers=HEADERS, json=payload)
        r.raise_for_status()
        return r.json()
async def n8n_patch(path, payload):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.patch(f"{N8N_URL}/api/v1{path}", headers=HEADERS, json=payload)
        r.raise_for_status()
        return r.json()

async def n8n_delete(path):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.delete(f"{N8N_URL}/api/v1{path}", headers=HEADERS)
        r.raise_for_status()
        return r.json()

# ─── OPERAÇÕES ──────────────────────────────────────────────────────────────────

async def list_workflows():
    r = await n8n_get("/workflows")
    return [{"id": w["id"], "name": w["name"], "active": w["active"]} for w in r.get("data", [])]

async def get_workflow(wf_id):
    return await n8n_get(f"/workflows/{wf_id}")

async def create_workflow(name, nodes, connections, active=False):
    payload = {"name": name, "nodes": nodes, "connections": connections,
                "settings": {"executionOrder": "v1"}}
    return await n8n_post("/workflows", payload)

async def activate_workflow(wf_id):
    return await n8n_patch(f"/workflows/{wf_id}", {"active": True})

async def deactivate_workflow(wf_id):
    return await n8n_patch(f"/workflows/{wf_id}", {"active": False})

async def delete_workflow(wf_id):
    return await n8n_delete(f"/workflows/{wf_id}")

async def list_executions(wf_id=None, limit=10):
    path = f"/executions?limit={limit}"
    if wf_id: path += f"&workflowId={wf_id}"
    return await n8n_get(path)

# ─── TEMPLATES COMPATÍVEIS COM N8N v2 ───────────────────────────────────────────

def tpl_manual_trigger():
    """Node de trigger manual — base para qualquer workflow."""
    return {
        "id": "manual-trigger",
        "name": "When clicking 'Test workflow'",
        "type": "n8n-nodes-base.manualTrigger",
        "typeVersion": 1,
        "position": [250, 300],
        "parameters": {}
    }

def tpl_webhook(path="jod-webhook", method="GET"):
    return {
        "id": "webhook-node",
        "name": "Webhook",
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 2,
        "position": [250, 300],
        "parameters": {
            "path": path,
            "httpMethod": method,
            "responseMode": "onReceived",
            "responseData": "allEntries"
        }
    }

def tpl_http_request(url, method="GET"):
    return {
        "id": "http-node",
        "name": "HTTP Request",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [500, 300],
        "parameters": {"url": url, "method": method}
    }

def tpl_code(js_code):
    return {
        "id": "code-node",
        "name": "Code",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [500, 300],
        "parameters": {
            "jsCode": js_code,
            "mode": "runOnceForAllItems"
        }
    }

def tpl_schedule(cron="0 9 * * 1-5"):
    return {
        "id": "schedule-node",
        "name": "Schedule Trigger",
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.2,
        "position": [250, 300],
        "parameters": {
            "rule": {"interval": [{"field": "cronExpression", "expression": cron}]}
        }
    }

def tpl_set(fields: dict):
    """Set node para definir valores."""
    assignments = [{"id": f"field-{i}", "name": k, "value": v, "type": "string"}
                   for i, (k, v) in enumerate(fields.items())]
    return {
        "id": "set-node",
        "name": "Set",
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [500, 300],
        "parameters": {
            "mode": "manual",
            "assignments": {"assignments": assignments}
        }
    }

def tpl_if(condition_left, operator, condition_right):
    """IF node para lógica condicional."""
    return {
        "id": "if-node",
        "name": "IF",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2,
        "position": [500, 300],
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True},
                "conditions": [{
                    "id": "cond-1",
                    "leftValue": condition_left,
                    "rightValue": condition_right,
                    "operator": {"type": "string", "operation": operator}
                }]
            }
        }
    }

def tpl_error_trigger():
    return {
        "id": "error-trigger",
        "name": "Error Trigger",
        "type": "n8n-nodes-base.errorTrigger",
        "typeVersion": 1,
        "position": [250, 300],
        "parameters": {}
    }

def tpl_respond_webhook(response="={{ $json }}"):
    return {
        "id": "respond-node",
        "name": "Respond to Webhook",
        "type": "n8n-nodes-base.respondToWebhook",
        "typeVersion": 1.1,
        "position": [750, 300],
        "parameters": {"respondWith": "json", "responseBody": response}
    }

# ─── WORKFLOWS PRONTOS ──────────────────────────────────────────────────────────

async def create_webhook_http(webhook_path="jod-webhook", target_url="https://httpbin.org/post"):
    """Webhook → HTTP Request → Respond."""
    nodes = [
        tpl_webhook(webhook_path, "POST"),
        tpl_http_request(target_url, "POST"),
        tpl_respond_webhook()
    ]
    connections = {
        "Webhook": {"main": [[{"node": "HTTP Request", "type": "main", "index": 0}]]},
        "HTTP Request": {"main": [[{"node": "Respond to Webhook", "type": "main", "index": 0}]]}
    }
    return await create_workflow(f"Webhook → HTTP ({webhook_path})", nodes, connections)

async def create_webhook_code(webhook_path="jod-code", js_code=None):
    """Webhook → Code Node → Respond."""
    if not js_code:
        js_code = """// Processa os dados recebidos
const items = $input.all();
return items.map(item => ({
  json: {
    ...item.json,
    processado: true,
    timestamp: new Date().toISOString()
  }
}));"""
    nodes = [
        tpl_webhook(webhook_path, "POST"),
        tpl_code(js_code),
        tpl_respond_webhook("={{ $json }}")
    ]
    connections = {
        "Webhook": {"main": [[{"node": "Code", "type": "main", "index": 0}]]},
        "Code": {"main": [[{"node": "Respond to Webhook", "type": "main", "index": 0}]]}
    }
    return await create_workflow(f"Webhook → Code ({webhook_path})", nodes, connections)

async def create_schedule_http(cron="0 9 * * 1-5", url="https://httpbin.org/get"):
    """Schedule → HTTP Request."""
    nodes = [tpl_schedule(cron), tpl_http_request(url)]
    connections = {
        "Schedule Trigger": {"main": [[{"node": "HTTP Request", "type": "main", "index": 0}]]}
    }
    return await create_workflow(f"Schedule → HTTP ({url[:30]})", nodes, connections)

async def create_error_handler(notify_url="https://httpbin.org/post"):
    """Error Trigger → HTTP notify."""
    nodes = [
        tpl_error_trigger(),
        tpl_code("""// Formata o erro para notificação
const error = $input.first().json;
return [{json: {
  workflow: error.workflow?.name || 'unknown',
  error: error.execution?.error?.message || 'unknown error',
  timestamp: new Date().toISOString()
}}];"""),
        tpl_http_request(notify_url, "POST")
    ]
    connections = {
        "Error Trigger": {"main": [[{"node": "Code", "type": "main", "index": 0}]]},
        "Code": {"main": [[{"node": "HTTP Request", "type": "main", "index": 0}]]}
    }
    return await create_workflow("Error Handler — JOD_ROBO", nodes, connections)

async def create_manual_code(js_code=None, name="Manual + Code"):
    """Manual Trigger → Code (para testes rápidos)."""
    if not js_code:
        js_code = """// Workflow de teste
return [{json: {
  status: 'ok',
  message: 'Workflow executado com sucesso',
  timestamp: new Date().toISOString()
}}];"""
    nodes = [tpl_manual_trigger(), tpl_code(js_code)]
    connections = {
        "When clicking 'Test workflow'": {"main": [[{"node": "Code", "type": "main", "index": 0}]]}
    }
    return await create_workflow(name, nodes, connections)

# ─── ROTEAMENTO POR DESCRIÇÃO ────────────────────────────────────────────────────

import re as _re

SYSTEM_AUTOMACAO = """Você é um arquiteto expert de automações n8n faixa preta.
Dado um objetivo, retorne APENAS JSON puro do workflow n8n completo e funcional.
REGRAS:
- JSON puro sem markdown, sem explicação
- Nodes completos: id, name, type, typeVersion, position, parameters
- Connections corretas entre todos os nodes
- Types válidos: n8n-nodes-base.webhook, n8n-nodes-base.code, n8n-nodes-base.httpRequest, n8n-nodes-base.set, n8n-nodes-base.scheduleTrigger, n8n-nodes-base.manualTrigger, n8n-nodes-base.respondToWebhook, n8n-nodes-base.telegram, n8n-nodes-base.emailSend
- Posições: x começa em 250, incrementa 250 por node, y=300
- JavaScript nos code nodes deve ser real e funcional
- Workflow funciona de ponta a ponta sem modificação
ESTRUTURA: {"name":"...","nodes":[...],"connections":{...},"settings":{"executionOrder":"v1"}}"""

async def arquitetar_workflow(descricao: str) -> dict:
    """LLM arquiteta o workflow completo baseado na descrição em linguagem natural."""
    resp = _groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_AUTOMACAO},
            {"role": "user", "content": f"Crie workflow n8n completo e funcional para: {descricao}"}
        ],
        temperature=0.1,
        max_tokens=4096
    )
    raw = resp.choices[0].message.content.strip()
    raw = _re.sub(r'```json\n?', '', raw)
    raw = _re.sub(r'```\n?', '', raw)
    raw = raw.strip()
    return _json.loads(raw)

async def create_from_description(description: str) -> dict:
    """Motor Universal: LLM arquiteta + n8n executa. Funciona para qualquer cenário."""
    try:
        wf_data = await arquitetar_workflow(description)
        wf_data["name"] = wf_data.get("name", f"X-Mom — {description[:50]}")
        result = await n8n_post("/workflows", wf_data)
        wf_id = result.get("id")
        return {
            "id": wf_id,
            "name": result.get("name"),
            "url": f"{N8N_URL}/workflow/{wf_id}",
            "status": "created",
            "nodes": len(wf_data.get("nodes", []))
        }
    except Exception as e:
        # Fallback para template manual se LLM falhar
        result = await create_manual_code(name=f"X-Mom — {description[:40]}")
        wf_id = result.get("id")
        return {"id": wf_id, "name": result.get("name"), "url": f"{N8N_URL}/workflow/{wf_id}", "status": "fallback", "error": str(e)}


if __name__ == "__main__":
    async def test():
        print("=== AGENTE N8N v2.0 ===\n")

        print("1. Listando workflows...")
        workflows = await list_workflows()
        print(f"   {len(workflows)} workflows encontrados")
        for w in workflows:
            print(f"   - [{w['id']}] {w['name']} (ativo: {w['active']})")

        print("\n2. Criando workflow webhook + code...")
        r = await create_webhook_code("teste-jod")
        print(f"   Criado: {r['name']} | ID: {r['id']}")

        print("\n3. Criando workflow schedule + http...")
        r2 = await create_schedule_http("0 8 * * 1-5", "https://httpbin.org/get")
        print(f"   Criado: {r2['name']} | ID: {r2['id']}")

        print(f"\n✅ Acesse em: {N8N_URL}")

    asyncio.run(test())
