#!/usr/bin/env python3
import asyncio,httpx,subprocess
from collections import deque
from pathlib import Path
LOG=Path(__file__).resolve().parent/"healing.log"
SVCS=[{"name":"eli-api","url":"http://localhost:37777/health","systemd":"eli-api"},{"name":"n8n-agent","url":"http://localhost:37780/health","systemd":"jod-n8n-agent"},{"name":"jod-telegram","url":None,"systemd":"jod-telegram"}]
_hist={s["name"]:deque(maxlen=10) for s in SVCS}
def _log(m):
    import datetime;e=f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {m}";print(e);open(LOG,"a").write(e+"\n")
async def check(svc):
    result={"name":svc["name"],"status":"ok","action":None}
    if svc["url"]:
        import time
        try:
            t0=time.time()
            async with httpx.AsyncClient(timeout=5.0) as c:r=await c.get(svc["url"])
            lat=time.time()-t0;_hist[svc["name"]].append(lat)
            h=list(_hist[svc["name"]])
            if len(h)>=5:
                if sum(h[-3:])/3>sum(h[:3])/3*2 and sum(h[-3:])/3>1.0:result["status"]="degraded";result["action"]="restart"
            if r.status_code>=500:result["status"]="error";result["action"]="restart"
        except:result["status"]="down";result["action"]="restart"
    else:
        rc=subprocess.run(f"systemctl is-active {svc['systemd']}",shell=True,capture_output=True,text=True)
        if rc.stdout.strip()!="active":result["status"]="down";result["action"]="restart"
    if result["action"]=="restart":
        _log(f"⚠ {svc['name']} {result['status']} — reiniciando")
        subprocess.run(f"sudo systemctl restart {svc['systemd']}",shell=True)
    return result
async def loop():
    _log("⚡ Predictive healing iniciado")
    while True:
        results=await asyncio.gather(*[check(s) for s in SVCS])
        issues=[r for r in results if r["status"]!="ok"]
        if issues:_log(f"Issues: {[i['name'] for i in issues]}")
        await asyncio.sleep(45)
if __name__=="__main__":asyncio.run(loop())
