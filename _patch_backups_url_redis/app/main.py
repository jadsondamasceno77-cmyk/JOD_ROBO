import os
import json
from datetime import datetime
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import redis

app = FastAPI(title="JOD Robo MVP")

REDIS_URL = os.getenv("URL_REDIS") or os.getenv("URL_REDIS") or os.getenv("REDIS_URL")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
GOOGLE_DIR = os.getenv("GOOGLE_DIR", "/google")

r = (redis.Redis.from_url(REDIS_URL, decode_responses=True)
     if REDIS_URL else redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True))

class Command(BaseModel):
    user_id: str = "jadson"
    command: str

@app.get("/health")
def health():
    try:
        r.ping()
        return {"ok": True, "redis": "up", "ts": datetime.utcnow().isoformat()}
    except Exception as e:
        return {"ok": False, "redis": "down", "error": str(e)}

@app.post("/command")
def command(payload: Command):
    # MVP: registra comando e deixa pronto para “executor” evoluir
    item = {
        "user_id": payload.user_id,
        "command": payload.command,
        "ts": datetime.utcnow().isoformat()
    }
    r.lpush(f"jod:commands:{payload.user_id}", json.dumps(item))
    return {"accepted": True, "queued": True, "item": item}

@app.get("/status/{user_id}")
def status(user_id: str):
    items = r.lrange(f"jod:commands:{user_id}", 0, 20)
    return {"user_id": user_id, "last_20": [json.loads(x) for x in items]}

@app.get("/")
def home():
    return {
        "name": "JOD Robo MVP",
        "endpoints": ["/health", "/command", "/status/{user_id}"],
        "google_dir_found": os.path.exists(GOOGLE_DIR),
        "google_files": sorted(os.listdir(GOOGLE_DIR)) if os.path.exists(GOOGLE_DIR) else []
    }

# UI (estilo chat)
app.mount("/ui", StaticFiles(directory="ui", html=True), name="ui")

@app.get("/")
def root_ui():
    return FileResponse("/app/ui/index.html")
