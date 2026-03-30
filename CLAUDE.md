# JOD_ROBO — Padrão de Arquitetura

## N8N Motor Cognitivo
Todo agente criado neste projeto TEM acesso ao motor n8n via HTTP interno.

### Como usar em qualquer agente:
```python
import httpx

async def executar_n8n(task: str, session_id: str = None) -> dict:
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post("http://localhost:37780/execute", json={
            "task": task,
            "session_id": session_id or "auto",
            "channel": "agent"
        })
        return r.json()
```

### Endpoints disponíveis (porta 37780):
- POST /execute — missão em linguagem natural via Groq + ferramentas reais
- GET  /workflows — listar workflows n8n
- POST /workflows/{id}/activate — ativar workflow
- POST /workflows/{id}/execute — executar workflow
- GET  /health — status do motor

### Regra obrigatória:
Nunca reimplementar conexão n8n. Sempre usar http://localhost:37780.
