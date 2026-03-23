import os, json
from supabase import create_client
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_KEY")

def get_client():
    return create_client(URL, KEY)

def select(table: str, limit=10):
    sb = get_client()
    r = sb.table(table).select("*").limit(limit).execute()
    return {"data": r.data, "count": len(r.data)}

def insert(table: str, data: dict):
    sb = get_client()
    r = sb.table(table).insert(data).execute()
    return {"inserted": r.data}

def health():
    try:
        sb = get_client()
        return {"status": "connected", "url": URL[:30]}
    except Exception as e:
        return {"status": "error", "reason": str(e)}

if __name__ == "__main__":
    print(json.dumps(health(), indent=2))
