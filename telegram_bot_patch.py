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
