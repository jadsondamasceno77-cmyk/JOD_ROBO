#!/usr/bin/env python3
"""JOD_ROBO — World State. Mantém modelo interno do projeto."""
import json
from pathlib import Path
from datetime import datetime

WS_PATH = Path(__file__).parent / "world_state.json"

def load():
    if WS_PATH.exists():
        return json.loads(WS_PATH.read_text())
    return {"decisions":[],"in_progress":[],"delivered":[],"last_updated":None}

def save(state):
    state["last_updated"] = datetime.now().isoformat()
    WS_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2))

def update(category, item):
    """category: decisions | in_progress | delivered"""
    state = load()
    state.setdefault(category, []).append({"item":item,"ts":datetime.now().isoformat()})
    state[category] = state[category][-50:]  # max 50 por categoria
    save(state)

def get_context():
    s = load()
    return json.dumps({
        "recent_decisions": s.get("decisions",[])[-5:],
        "in_progress": s.get("in_progress",[])[-3:],
        "last_delivered": s.get("delivered",[])[-3:]
    }, ensure_ascii=False)

if __name__ == "__main__":
    print(get_context())
