import json, os
import chromadb
from pathlib import Path

DB_PATH = str(Path(__file__).resolve().parent.parent.parent / "memory" / "chroma_db")
client = chromadb.PersistentClient(path=DB_PATH)
collection = client.get_or_create_collection("jod_memoria")

def store(doc_id: str, text: str, metadata: dict = None):
    collection.upsert(documents=[text], ids=[doc_id], metadatas=[metadata or {}])
    return {"stored": doc_id}

def search(query: str, n=3):
    results = collection.query(query_texts=[query], n_results=n)
    return {"results": results["documents"][0] if results["documents"] else []}

def list_all():
    return {"count": collection.count()}

if __name__ == "__main__":
    store("test-001", "JOD_ROBO sistema autonomo de agentes", {"source": "system"})
    r = search("agentes autonomos")
    print(json.dumps(r, indent=2))
    print(json.dumps(list_all(), indent=2))
