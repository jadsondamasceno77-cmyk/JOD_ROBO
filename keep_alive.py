#!/usr/bin/env python3
import asyncio,httpx
async def keep_alive():
    print("[KEEP-ALIVE] iniciado — ping a cada 30s")
    while True:
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                await c.get("http://localhost:37779/health")
        except:pass
        await asyncio.sleep(30)
if __name__=="__main__":asyncio.run(keep_alive())
