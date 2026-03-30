#!/usr/bin/env python3
"""
Deploy Manager — controla todas as 10 mães Oracle remotamente.
Monitora saúde, distribui tarefas, registra novas instâncias.
"""
import os
import json
import asyncio
import httpx
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="JOD Deploy Manager", version="1.0")

INSTANCES_FILE = Path(__file__).parent / "instances.json"
NICHE_CONFIG   = Path(__file__).parent / "niche_config.json"
_TOKEN         = os.getenv("JOD_TRUST_MANIFEST", "jod_robo_trust_2026_secure")

# ─── Storage ──────────────────────────────────────────────────────────────────

def _load_instances() -> dict:
    if INSTANCES_FILE.exists():
        return json.loads(INSTANCES_FILE.read_text())
    return {}

def _save_instances(data: dict):
    INSTANCES_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))

def _load_niches() -> list:
    if NICHE_CONFIG.exists():
        return json.loads(NICHE_CONFIG.read_text())["maes"]
    return []

# ─── Models ───────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    instance_id: str
    ip: str
    niche: str
    country: str
    eli_url: str
    n8n_url: str

class TaskRequest(BaseModel):
    instance_id: Optional[str] = None  # None = broadcast para todas
    task: str
    session_id: str = "deploy"

# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.post("/register")
async def register_instance(r: RegisterRequest):
    """Instância Oracle recém-instalada se registra aqui."""
    instances = _load_instances()
    instances[r.instance_id] = {
        "ip": r.ip,
        "niche": r.niche,
        "country": r.country,
        "eli_url": r.eli_url,
        "n8n_url": r.n8n_url,
        "registered_at": datetime.now().isoformat(),
        "status": "online",
        "profiles_created": 0,
        "interactions_today": 0,
    }
    _save_instances(instances)
    print(f"[+] Nova mãe registrada: {r.instance_id} ({r.ip}) — {r.niche}/{r.country}")
    return {"status": "registered", "instance_id": r.instance_id}

@app.get("/instances")
async def list_instances():
    """Lista todas as mães registradas."""
    return _load_instances()

@app.get("/health")
async def manager_health():
    instances = _load_instances()
    return {
        "status": "ok",
        "total_maes": len(instances),
        "manager": "deploy_manager",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/status")
async def full_status():
    """Verifica saúde de todas as mães em paralelo."""
    instances = _load_instances()
    results = {}

    async def _check(iid, data):
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                r = await c.get(f"{data['eli_url']}/health")
                results[iid] = {**data, "health": r.json(), "online": True}
        except Exception as e:
            results[iid] = {**data, "online": False, "error": str(e)}

    await asyncio.gather(*[_check(iid, d) for iid, d in instances.items()])
    online = sum(1 for v in results.values() if v.get("online"))
    return {
        "total": len(results),
        "online": online,
        "offline": len(results) - online,
        "instances": results
    }

@app.post("/task")
async def send_task(r: TaskRequest):
    """Envia tarefa para 1 mãe ou todas (broadcast)."""
    instances = _load_instances()
    targets = (
        {r.instance_id: instances[r.instance_id]}
        if r.instance_id and r.instance_id in instances
        else instances
    )

    results = {}

    async def _send(iid, data):
        try:
            async with httpx.AsyncClient(timeout=60.0) as c:
                resp = await c.post(
                    f"{data['eli_url']}/agent-os",
                    headers={"x-jod-token": _TOKEN},
                    json={"task": r.task, "session_id": r.session_id}
                )
                results[iid] = resp.json()
        except Exception as e:
            results[iid] = {"error": str(e)}

    await asyncio.gather(*[_send(iid, d) for iid, d in targets.items()])
    return {"sent_to": len(results), "results": results}

@app.get("/deploy-next")
async def deploy_next():
    """Retorna config da próxima mãe a ser implantada."""
    instances = _load_instances()
    niches = _load_niches()
    deployed_ids = set(instances.keys())
    for niche in niches:
        if niche["instance_id"] not in deployed_ids:
            return {
                "status": "pending",
                "next": niche,
                "setup_command": (
                    f"bash setup_oracle.sh "
                    f"--instance-id {niche['instance_id']} "
                    f"--niche {niche['niche']} "
                    f"--country {niche['country']} "
                    f"--groq-key $GROQ_API_KEY "
                    f"--central http://SEU_IP_LOCAL:38000"
                )
            }
    return {"status": "all_deployed", "total": len(niches)}

@app.get("/summary")
async def summary():
    """Resumo geral do ecossistema."""
    instances = _load_instances()
    niches = _load_niches()
    total_profiles = sum(v.get("profiles_created", 0) for v in instances.values())
    total_interactions = sum(v.get("interactions_today", 0) for v in instances.values())
    return {
        "maes_configuradas": len(niches),
        "maes_implantadas": len(instances),
        "maes_pendentes": len(niches) - len(instances),
        "perfis_criados_total": total_profiles,
        "interacoes_hoje": total_interactions,
        "paises": list({v["country"] for v in instances.values()}),
        "nichos": list({v["niche"] for v in instances.values()}),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=38000)
