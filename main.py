import os, sys, uuid, json, shutil, asyncio, logging, hmac, hashlib, subprocess
from pathlib import Path
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Literal, Annotated, Union
from fastapi import FastAPI, HTTPException, Header, Request, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, String, Text, DateTime, Integer, select
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
AGENTS_DIR = BASE_DIR / "agents"
TEMPLATES_DIR = BASE_DIR / "templates"
MEMORY_DIR = BASE_DIR / "memory"
SNAPSHOTS_DIR = BASE_DIR / "snapshots"
DB_PATH = MEMORY_DIR / "jod_core.db"
for d in [AGENTS_DIR, TEMPLATES_DIR, MEMORY_DIR, SNAPSHOTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

load_dotenv(BASE_DIR / ".env")
TRUST_TOKEN = os.getenv("JOD_TRUST_MANIFEST", "")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
logger = logging.getLogger("JOD_FACTORY")
if not TRUST_TOKEN:
    logger.error("ERRO CRITICO: JOD_TRUST_MANIFEST nao configurado.")
    sys.exit(1)

AgentStatus = Literal["draft","validated","needs_approval","active","inactive","failed"]
TaskStatus = Literal["queued","plan","dry_run","running","needs_approval","succeeded","failed","rolled_back","dead_letter"]
ExecMode = Literal["plan","dry_run","apply"]
AgentSpecialty = Literal["executor","analyzer","crawler","scheduler","support"]

class AgentManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    agent_id: str; name: str; specialty: AgentSpecialty; entrypoint: str
    allowed_actions: List[str] = Field(default_factory=list)
    allowed_paths: List[str] = Field(default_factory=list)
    allowed_hosts: List[str] = Field(default_factory=list)
    required_env: List[str] = Field(default_factory=list)
    version: str = "1.0.0"; status: AgentStatus = "draft"

class BaseCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action_type: str; mode: ExecMode = "apply"; retry_count: int = 0

class CreateAgentTemplateParams(BaseModel):
    template_name: AgentSpecialty
    new_agent_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    name: str

class CloneAgentParams(BaseModel):
    source_agent_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    new_agent_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")

class ValidateAgentParams(BaseModel):
    agent_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")

class ActivateAgentParams(BaseModel):
    agent_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")

class CmdCreateTemplate(BaseCommand):
    action_type: Literal["create_agent_from_template"]; parameters: CreateAgentTemplateParams

class CmdClone(BaseCommand):
    action_type: Literal["clone_agent"]; parameters: CloneAgentParams

class CmdValidate(BaseCommand):
    action_type: Literal["validate_agent"]; parameters: ValidateAgentParams

class CmdActivate(BaseCommand):
    action_type: Literal["activate_agent"]; parameters: ActivateAgentParams

Command = Annotated[Union[CmdCreateTemplate,CmdClone,CmdValidate,CmdActivate], Field(discriminator="action_type")]

class RequestHeaders(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    x_trust_token: str = Field(min_length=8)
    x_request_id: str = Field(min_length=8)
    x_idempotency_key: str = Field(min_length=8)

async def get_validated_headers(x_trust_token: str=Header(...), x_request_id: str=Header(...), x_idempotency_key: str=Header(...)) -> RequestHeaders:
    h = RequestHeaders(x_trust_token=x_trust_token, x_request_id=x_request_id, x_idempotency_key=x_idempotency_key)
    if not hmac.compare_digest(h.x_trust_token.encode(), TRUST_TOKEN.encode()):
        raise HTTPException(status_code=401, detail="Token invalido.")
    return h

class TaskAcceptedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    task_id: str; status: str; queued_at: str

Base = declarative_base()

class TaskDB(Base):
    __tablename__ = "tasks"
    id = Column(String, primary_key=True); status = Column(String)
    action_type = Column(String); payload = Column(Text)
    result = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=True)

class TaskEventDB(Base):
    __tablename__ = "task_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String); event = Column(String); detail = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class AgentDB(Base):
    __tablename__ = "agents"
    id = Column(String, primary_key=True); status = Column(String)
    version = Column(String); manifest = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class AgentVersionDB(Base):
    __tablename__ = "agent_versions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String); version = Column(String); manifest = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class TemplateDB(Base):
    __tablename__ = "templates"
    id = Column(String, primary_key=True); description = Column(String)

class AuditLogDB(Base):
    __tablename__ = "audit_logs"
    id = Column(String, primary_key=True); task_id = Column(String); action = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class IdempotencyDB(Base):
    __tablename__ = "idempotency_keys"
    key = Column(String, primary_key=True); task_id = Column(String); payload_hash = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class SnapshotDB(Base):
    __tablename__ = "snapshots"
    id = Column(String, primary_key=True); agent_id = Column(String); filepath = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

engine = create_async_engine(f"sqlite+aiosqlite:///{DB_PATH}", echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class DomainError(Exception):
    def __init__(self, code, message, status_code=400):
        self.code = code; self.message = message; self.status_code = status_code

async def domain_error_handler(request, exc):
    return JSONResponse(status_code=exc.status_code, content={"error_code": exc.code, "message": exc.message})

def safe_path(base, name):
    if "/" in name or "\\" in name or ".." in name:
        raise DomainError("path_traversal", "Caminho invalido.", 403)
    resolved = (base / name).resolve()
    if base not in resolved.parents and resolved != base:
        raise DomainError("path_escape", "Fuga de diretorio.", 403)
    return resolved

class StateEngine:
    def __init__(self): self.queue = asyncio.Queue()
    async def get_or_set_idempotency(self, ikey, cmd):
        phash = hashlib.sha256(cmd.model_dump_json(exclude={"task_id"}).encode()).hexdigest()
        async with AsyncSessionLocal() as session:
            record = await session.get(IdempotencyDB, ikey)
            if record:
                if record.payload_hash != phash:
                    raise DomainError("idempotency_conflict", "Payload diferente.", 409)
                return record.task_id
            session.add_all([
                IdempotencyDB(key=ikey, task_id=cmd.task_id, payload_hash=phash),
                TaskDB(id=cmd.task_id, status="queued", action_type=cmd.action_type, payload=cmd.model_dump_json())
            ])
            await session.commit()
        return cmd.task_id
    async def update_task(self, task_id, status, result=None, event=None):
        async with AsyncSessionLocal() as session:
            task = await session.get(TaskDB, task_id)
            if task:
                task.status = status; task.updated_at = datetime.now(timezone.utc)
                if result: task.result = json.dumps(result)
                if event: session.add(TaskEventDB(task_id=task_id, event=event, detail=json.dumps(result or {})))
                await session.commit()

state = StateEngine()

class SnapshotManager:
    @staticmethod
    async def create(agent_id):
        agent_path = safe_path(AGENTS_DIR, agent_id)
        if not agent_path.exists(): return None
        snap_id = f"snap_{agent_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        snap_path = SNAPSHOTS_DIR / snap_id
        shutil.make_archive(str(snap_path), "zip", str(agent_path))
        async with AsyncSessionLocal() as session:
            session.add(SnapshotDB(id=snap_id, agent_id=agent_id, filepath=f"{snap_path}.zip"))
            await session.commit()
        return snap_id
    @staticmethod
    async def rollback(agent_id, snap_id):
        snap_path = SNAPSHOTS_DIR / f"{snap_id}.zip"
        if not snap_path.exists(): raise Exception("Snapshot nao encontrado.")
        agent_path = safe_path(AGENTS_DIR, agent_id)
        if agent_path.exists(): shutil.rmtree(agent_path)
        shutil.unpack_archive(str(snap_path), str(agent_path))

async def validate_manifest_logic(agent_id):
    a_path = safe_path(AGENTS_DIR, agent_id)
    m_path = a_path / "manifest.json"
    if not m_path.exists(): return {"valid": False, "reason": "Manifest missing"}
    try:
        with open(m_path) as f: data = json.load(f)
        manifest = AgentManifest.model_validate(data)
        if manifest.agent_id != agent_id: return {"valid": False, "reason": "agent_id mismatch"}
        entry = a_path / manifest.entrypoint
        if not entry.exists(): return {"valid": False, "reason": "Entrypoint missing"}
        if entry.suffix == ".py":
            proc = subprocess.run([sys.executable, "-m", "py_compile", str(entry)], capture_output=True, text=True)
            if proc.returncode != 0: return {"valid": False, "reason": f"Syntax error: {proc.stderr}"}
        return {"valid": True, "manifest": data}
    except Exception as e:
        return {"valid": False, "reason": str(e)}

async def process_queue():
    while True:
        cmd = await state.queue.get()
        result = {}; final_status = "succeeded"; snap_id = None
        try:
            await state.update_task(cmd.task_id, "running", event=f"Started {cmd.action_type}")
            if cmd.action_type == "create_agent_from_template":
                t_path = safe_path(TEMPLATES_DIR, cmd.parameters.template_name)
                a_path = safe_path(AGENTS_DIR, cmd.parameters.new_agent_id)
                if not t_path.exists(): raise DomainError("template_not_found", "Template nao existe.", 404)
                if a_path.exists(): raise DomainError("agent_exists", "Agente ja existe.", 409)
                if cmd.mode == "plan": result = {"plan": f"Copiar {cmd.parameters.template_name} -> {cmd.parameters.new_agent_id}"}
                elif cmd.mode == "apply":
                    shutil.copytree(t_path, a_path)
                    manifest = AgentManifest(agent_id=cmd.parameters.new_agent_id, name=cmd.parameters.name, specialty=cmd.parameters.template_name, entrypoint="main.py")
                    with open(a_path / "manifest.json", "w") as f: f.write(manifest.model_dump_json(indent=2))
                    async with AsyncSessionLocal() as session:
                        session.add(AgentDB(id=manifest.agent_id, status="draft", version=manifest.version, manifest=manifest.model_dump_json()))
                        await session.commit()
                    result = {"status": "created_as_draft", "agent_id": manifest.agent_id}
            elif cmd.action_type == "clone_agent":
                source = safe_path(AGENTS_DIR, cmd.parameters.source_agent_id)
                target = safe_path(AGENTS_DIR, cmd.parameters.new_agent_id)
                if not source.exists(): raise DomainError("agent_not_found", "Origem nao encontrada.", 404)
                if target.exists(): raise DomainError("clone_conflict", "Destino ja existe.", 409)
                if cmd.mode == "plan": result = {"plan": f"Clonar {cmd.parameters.source_agent_id}"}
                elif cmd.mode == "apply":
                    shutil.copytree(source, target)
                    m_path = target / "manifest.json"
                    if m_path.exists():
                        with open(m_path) as f: old_m = json.load(f)
                        old_m["agent_id"] = cmd.parameters.new_agent_id; old_m["status"] = "draft"
                        manifest = AgentManifest.model_validate(old_m)
                        with open(m_path, "w") as f: f.write(manifest.model_dump_json(indent=2))
                        async with AsyncSessionLocal() as session:
                            session.add(AgentDB(id=manifest.agent_id, status="draft", version=manifest.version, manifest=manifest.model_dump_json()))
                            await session.commit()
                    result = {"status": "cloned_as_draft", "agent_id": cmd.parameters.new_agent_id}
            elif cmd.action_type == "validate_agent":
                if cmd.mode == "plan": result = {"plan": f"Validar {cmd.parameters.agent_id}"}
                elif cmd.mode == "apply":
                    val_res = await validate_manifest_logic(cmd.parameters.agent_id)
                    async with AsyncSessionLocal() as session:
                        ag = await session.get(AgentDB, cmd.parameters.agent_id)
                        if ag: ag.status = "validated" if val_res["valid"] else "failed"; await session.commit()
                    if not val_res["valid"]: raise Exception(f"Validation failed: {val_res['reason']}")
                    result = val_res
            elif cmd.action_type == "activate_agent":
                async with AsyncSessionLocal() as session:
                    ag = await session.get(AgentDB, cmd.parameters.agent_id)
                    if not ag: raise DomainError("agent_not_found", "Agente nao encontrado.", 404)
                    if ag.status != "validated": raise DomainError("invalid_state", f"Status: {ag.status}. Rode validate_agent primeiro.", 403)
                    if cmd.mode == "plan": result = {"plan": "Snapshot e ativar."}
                    elif cmd.mode == "apply":
                        snap_id = await SnapshotManager.create(cmd.parameters.agent_id)
                        ag.status = "active"
                        m_path = safe_path(AGENTS_DIR, cmd.parameters.agent_id) / "manifest.json"
                        with open(m_path) as f: m_data = json.load(f)
                        m_data["status"] = "active"
                        with open(m_path, "w") as f: json.dump(m_data, f, indent=2)
                        await session.commit()
                        result = {"status": "activated", "snapshot": snap_id}
        except Exception as e:
            logger.error(f"Erro Task {cmd.task_id}: {e}")
            result = {"error": str(e)}
            if snap_id and cmd.mode == "apply":
                try:
                    tid = getattr(cmd.parameters, "agent_id", getattr(cmd.parameters, "new_agent_id", None))
                    if tid: await SnapshotManager.rollback(tid, snap_id)
                    final_status = "rolled_back"
                except: final_status = "failed"
            else: final_status = "failed"
        finally:
            await state.update_task(cmd.task_id, final_status, result, event=final_status)
            state.queue.task_done()

async def setup_base_templates():
    for t in ["executor","analyzer","crawler","scheduler","support"]:
        t_path = TEMPLATES_DIR / t
        t_path.mkdir(parents=True, exist_ok=True)
        if not (t_path / "main.py").exists():
            with open(t_path / "main.py", "w") as f: f.write(f"print('Hello from {t}')")

@asynccontextmanager
async def lifespan(app):
    async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
    await setup_base_templates()
    w = asyncio.create_task(process_queue())
    logger.info("JOD_FACTORY UP.")
    yield
    w.cancel()

app = FastAPI(title="JOD_FACTORY", version="2.0", lifespan=lifespan)
app.add_exception_handler(DomainError, domain_error_handler)

async def _enqueue(cmd, h):
    task_id = await state.get_or_set_idempotency(h.x_idempotency_key, cmd)
    if task_id != cmd.task_id:
        return TaskAcceptedResponse(task_id=task_id, status="already_queued", queued_at=datetime.now(timezone.utc).isoformat())
    await state.queue.put(cmd)
    return TaskAcceptedResponse(task_id=cmd.task_id, status="queued", queued_at=datetime.now(timezone.utc).isoformat())

@app.post("/agents/create-from-template", status_code=202)
async def api_create(cmd: CmdCreateTemplate, h: RequestHeaders=Depends(get_validated_headers)): return await _enqueue(cmd, h)

@app.post("/agents/clone", status_code=202)
async def api_clone(cmd: CmdClone, h: RequestHeaders=Depends(get_validated_headers)): return await _enqueue(cmd, h)

@app.post("/agents/validate", status_code=202)
async def api_validate(cmd: CmdValidate, h: RequestHeaders=Depends(get_validated_headers)): return await _enqueue(cmd, h)

@app.post("/agents/activate", status_code=202)
async def api_activate(cmd: CmdActivate, h: RequestHeaders=Depends(get_validated_headers)): return await _enqueue(cmd, h)

@app.get("/tasks")
async def list_tasks(limit: int=10, h: RequestHeaders=Depends(get_validated_headers)):
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(TaskDB).order_by(TaskDB.created_at.desc()).limit(limit))
        return [{"id": t.id, "status": t.status, "action": t.action_type} for t in res.scalars()]

@app.get("/tasks/{task_id}")
async def get_task(task_id: str, h: RequestHeaders=Depends(get_validated_headers)):
    async with AsyncSessionLocal() as session:
        t = await session.get(TaskDB, task_id)
        if not t: raise DomainError("not_found", "Task nao encontrada", 404)
        return {"id": t.id, "status": t.status, "result": json.loads(t.result) if t.result else None}

@app.get("/agents")
async def list_agents(h: RequestHeaders=Depends(get_validated_headers)):
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(AgentDB))
        return [{"id": a.id, "status": a.status, "version": a.version} for a in res.scalars()]

@app.get("/agents/{agent_id}")
async def get_agent(agent_id: str, h: RequestHeaders=Depends(get_validated_headers)):
    async with AsyncSessionLocal() as session:
        a = await session.get(AgentDB, agent_id)
        if not a: raise DomainError("not_found", "Agente nao encontrado", 404)
        return {"id": a.id, "status": a.status, "version": a.version, "manifest": json.loads(a.manifest) if a.manifest else None}

@app.get("/templates")
async def list_templates(h: RequestHeaders=Depends(get_validated_headers)):
    return {"templates": [d.name for d in TEMPLATES_DIR.iterdir() if d.is_dir()]}

@app.get("/audit")
async def list_audit(limit: int=10, h: RequestHeaders=Depends(get_validated_headers)):
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(TaskEventDB).order_by(TaskEventDB.created_at.desc()).limit(limit))
        return [{"task_id": ev.task_id, "event": ev.event, "time": ev.created_at.isoformat()} for ev in res.scalars()]

@app.get("/health/live")
async def health_live(): return {"status": "alive"}

@app.get("/health/ready")
async def health_ready(): return {"status": "ready", "queue_size": state.queue.qsize(), "db_path": str(DB_PATH)}
