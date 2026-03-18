import asyncio
import json
import logging
import os
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Optional

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, DateTime, Integer, String, Text, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent.resolve()
AGENTS_DIR = BASE_DIR / "agents"
TEMPLATES_DIR = BASE_DIR / "templates"
LOCAL_AI_URL = os.getenv("LOCAL_AI_URL", "http://127.0.0.1:11434/api/generate")
LOCAL_AI_MODEL            = os.getenv("LOCAL_AI_MODEL",            "gemma3:4b")
LOCAL_AI_STRUCTURED_MODEL = os.getenv("LOCAL_AI_STRUCTURED_MODEL", "functiongemma")
API_TOKEN = os.getenv("JOD_ROBO_API_TOKEN", "dev-token")
DB_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/jod_robo.db")
_SELF_BASE_URL = f"http://127.0.0.1:{os.getenv('SERVER_PORT', '37777')}"

AGENTS_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
import json as _json_log
from contextvars import ContextVar

_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")

class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        from datetime import datetime, timezone
        payload = {
            "ts":             datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{int(record.created % 1 * 1e6):06d}",
            "level":          record.levelname,
            "event":          record.getMessage(),
            "logger":         record.name,
            "correlation_id": _correlation_id.get(""),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        _skip = {
            "msg","args","levelname","levelno","pathname","filename","module",
            "exc_info","exc_text","stack_info","lineno","funcName","created",
            "msecs","relativeCreated","thread","threadName","processName",
            "process","name","message",
        }
        for k, v in record.__dict__.items():
            if k not in _skip:
                payload[k] = v
        return _json_log.dumps(payload, ensure_ascii=False, default=str)

def _setup_logging() -> logging.Logger:
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    logger = logging.getLogger("jod_robo")
    logger.setLevel(logging.INFO)
    logger.handlers = [handler]
    logger.propagate = False
    return logger

log = _setup_logging()

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as _Request
import uuid as _uuid_mw

class _CorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: _Request, call_next):
        cid = request.headers.get("X-Correlation-Id") or str(_uuid_mw.uuid4())
        token = _correlation_id.set(cid)
        try:
            response = await call_next(request)
            response.headers["X-Correlation-Id"] = cid
            return response
        finally:
            _correlation_id.reset(token)

# serialização por target_path
import asyncio as _asyncio
_path_locks: dict[str, _asyncio.Lock] = {}
_path_locks_mutex: _asyncio.Lock = _asyncio.Lock()

async def _get_path_lock(target_path: str) -> _asyncio.Lock:
    async with _path_locks_mutex:
        if target_path not in _path_locks:
            _path_locks[target_path] = _asyncio.Lock()
        return _path_locks[target_path]


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
engine = create_engine(DB_URL, connect_args={"check_same_thread": False} if "sqlite" in DB_URL else {})
Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class AgentStatus(str, Enum):
    draft = "draft"
    validated = "validated"
    active = "active"
    inactive = "inactive"


class AgentRecord(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(120), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    template_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=AgentStatus.draft)
    cloned_from: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Finalizer Agent — DB models
# ---------------------------------------------------------------------------
class FinalizerManifestRecord(Base):
    __tablename__ = "finalizer_manifests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    allowed_actions: Mapped[str] = mapped_column(Text, nullable=False)   # JSON array
    allowed_paths: Mapped[str] = mapped_column(Text, nullable=False)      # JSON array
    forbidden_paths: Mapped[str] = mapped_column(Text, nullable=False)    # JSON array
    allowed_hosts: Mapped[str] = mapped_column(Text, nullable=False)      # JSON array
    requires_approval: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class FinalizerSnapshotRecord(Base):
    __tablename__ = "finalizer_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id: Mapped[str] = mapped_column(String(36), nullable=False)
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    content_before: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rolled_back: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class FinalizerAuditRecord(Base):
    __tablename__ = "finalizer_audit"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id: Mapped[str] = mapped_column(String(36), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class GuardianAuditRecord(Base):
    __tablename__ = "guardian_audit"

    id:       Mapped[str]      = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id: Mapped[str]      = mapped_column(String(36), nullable=False)
    action:   Mapped[str]      = mapped_column(String(120), nullable=False)
    status:   Mapped[str]      = mapped_column(String(40), nullable=False)
    details:  Mapped[str]      = mapped_column(Text, nullable=False, default="{}")
    ts:       Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class IntegrationAuditRecord(Base):
    __tablename__ = "integration_audit"

    id:              Mapped[str]           = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    finalizer_id:    Mapped[str]           = mapped_column(String(36), nullable=False)
    guardian_id:     Mapped[str]           = mapped_column(String(36), nullable=False)
    action:          Mapped[str]           = mapped_column(String(120), nullable=False)
    target_path:     Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    transaction_id:  Mapped[str]           = mapped_column(String(36), nullable=False)
    guardian_status: Mapped[str]           = mapped_column(String(40), nullable=False)

    io_committed:      Mapped[bool]               = mapped_column(Boolean, nullable=False, default=False)
    io_failure_reason: Mapped[Optional[str]]      = mapped_column(Text, nullable=True, default=None)
    io_finalized_at:   Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

    ts:              Mapped[datetime]      = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


Base.metadata.create_all(engine)


def _migrate_mission_log(engine) -> None:
    """
    Cria a tabela mission_log se ainda não existir.
    Idempotente: CREATE TABLE IF NOT EXISTS não falha em reinicializações.
    """
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS mission_log (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                mission_id     TEXT    NOT NULL,
                correlation_id TEXT,
                finalizer_id   TEXT    NOT NULL,
                guardian_id    TEXT,
                action         TEXT    NOT NULL,
                target_path    TEXT,
                status         TEXT    NOT NULL,
                io_committed   INTEGER,
                transaction_id TEXT,
                details        TEXT,
                created_at     DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()


def _migrate_mission_control(engine) -> None:
    """
    Cria tabela mission_control e adiciona step_index a mission_log. Idempotente.
    """
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS mission_control (
                mission_id   TEXT    PRIMARY KEY,
                status       TEXT    NOT NULL DEFAULT 'PENDING',
                owner_id     TEXT,
                lock_version INTEGER NOT NULL DEFAULT 0,
                heartbeat_at TEXT,
                claimed_at   TEXT,
                current_step INTEGER NOT NULL DEFAULT 0,
                created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """))
        conn.commit()

        result  = conn.execute(text("PRAGMA table_info(mission_log)"))
        existing = {row[1] for row in result.fetchall()}
        if "step_index" not in existing:
            conn.execute(text("ALTER TABLE mission_log ADD COLUMN step_index INTEGER"))
            conn.commit()


def _migrate_macrobloco_a(engine) -> None:
    """
    Cria tabelas e colunas do MACROBLOCO A. Idempotente.
    - approval_requests: nova tabela (UNIQUE por mission_id+step_index)
    - circuit_breaker: nova tabela (PK por provider_id+operation)
    - mission_control: colunas max_retries, retry_delay_secs, retry_count, next_retry_at
    - mission_log: coluna retry_count
    """
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS approval_requests (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                mission_id       TEXT    NOT NULL,
                step_index       INTEGER NOT NULL,
                context_snapshot TEXT    NOT NULL,
                status           TEXT    NOT NULL DEFAULT 'PENDING',
                decided_by       TEXT,
                notes            TEXT,
                decided_at       TEXT,
                expires_at       TEXT    NOT NULL,
                created_at       TEXT    NOT NULL,
                UNIQUE(mission_id, step_index)
            )
        """))
        conn.commit()

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS circuit_breaker (
                provider_id  TEXT    NOT NULL,
                operation    TEXT    NOT NULL,
                state        TEXT    NOT NULL DEFAULT 'CLOSED',
                failures     INTEGER NOT NULL DEFAULT 0,
                opened_at    TEXT,
                PRIMARY KEY (provider_id, operation)
            )
        """))
        conn.commit()

        mc_existing = {row[1] for row in conn.execute(
            text("PRAGMA table_info(mission_control)")
        ).fetchall()}
        for col, defn in {
            "max_retries":      "INTEGER DEFAULT 3",
            "retry_delay_secs": "REAL DEFAULT 2.0",
            "retry_count":      "INTEGER DEFAULT 0",
            "next_retry_at":    "TEXT",
        }.items():
            if col not in mc_existing:
                conn.execute(text(f"ALTER TABLE mission_control ADD COLUMN {col} {defn}"))
                conn.commit()

        ml_existing = {row[1] for row in conn.execute(
            text("PRAGMA table_info(mission_log)")
        ).fetchall()}
        if "retry_count" not in ml_existing:
            conn.execute(text("ALTER TABLE mission_log ADD COLUMN retry_count INTEGER DEFAULT 0"))
            conn.commit()


def _migrate_macrobloco_d(engine) -> None:
    """
    Adiciona context_json em mission_control para redespacho formal do watchdog.
    Idempotente: verifica via PRAGMA antes de ALTER TABLE.
    """
    with engine.connect() as conn:
        existing = {row[1] for row in conn.execute(
            text("PRAGMA table_info(mission_control)")
        ).fetchall()}
        if "context_json" not in existing:
            conn.execute(text("ALTER TABLE mission_control ADD COLUMN context_json TEXT"))
            conn.commit()


def _migrate_integration_audit(engine) -> None:
    """
    Adiciona colunas B1 em integration_audit se ainda não existirem.
    Idempotente: verifica via PRAGMA antes de cada ALTER TABLE.
    """
    new_columns = {
        "io_committed":      "INTEGER NOT NULL DEFAULT 0",
        "io_failure_reason": "TEXT",
        "io_finalized_at":   "TEXT",
    }

    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(integration_audit)"))
        existing = {row[1] for row in result.fetchall()}

        for col, definition in new_columns.items():
            if col not in existing:
                conn.execute(
                    text(f"ALTER TABLE integration_audit ADD COLUMN {col} {definition}")
                )
                conn.commit()


# ---------------------------------------------------------------------------
# Async task queue
# ---------------------------------------------------------------------------
task_queue: asyncio.Queue = asyncio.Queue()
_worker_task:      Optional[asyncio.Task]  = None
_watchdog_stop:    Optional[asyncio.Event] = None
_watchdog_task:    Optional[asyncio.Task]  = None
_watchdog_scanner                          = None  # WatchdogScanner, set in lifespan


async def _queue_worker():
    while True:
        job = await task_queue.get()
        try:
            fn, args, kwargs, fut = job
            result = await fn(*args, **kwargs)
            if not fut.done():
                fut.set_result(result)
        except Exception as exc:
            if not fut.done():
                fut.set_exception(exc)
        finally:
            task_queue.task_done()


async def enqueue(fn, *args, **kwargs):
    loop = asyncio.get_event_loop()
    fut = loop.create_future()
    await task_queue.put((fn, args, kwargs, fut))
    return await fut


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _worker_task, _watchdog_stop, _watchdog_task, _watchdog_scanner

    _migrate_integration_audit(engine)
    _migrate_mission_log(engine)
    _migrate_mission_control(engine)
    _migrate_macrobloco_a(engine)
    _migrate_memory_service(engine)
    _migrate_macrobloco_d(engine)

    # Startup sweep: remove shadow files (.*.jod_tmp) deixados por crashes anteriores
    for _tmp in BASE_DIR.rglob(".*.jod_tmp"):
        try:
            _tmp.unlink()
            log.warning("lifespan sweep: removido shadow file órfão %s", _tmp)
        except OSError as _exc:
            log.error("lifespan sweep: falha ao remover %s: %s", _tmp, _exc)
    _worker_task = asyncio.create_task(_queue_worker())
    log.info("Queue worker started")

    _watchdog_stop = asyncio.Event()
    _watchdog_scanner = WatchdogScanner(Session, _redispatch_mission)
    _watchdog_task = asyncio.create_task(_watchdog_scanner.run_loop(_watchdog_stop))
    log.info("Watchdog started")

    yield

    _worker_task.cancel()
    try:
        await _worker_task
    except asyncio.CancelledError:
        pass
    log.info("Queue worker stopped")

    _watchdog_stop.set()
    _watchdog_task.cancel()
    try:
        await _watchdog_task
    except asyncio.CancelledError:
        pass
    log.info("Watchdog stopped")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="JOD_ROBO fase2",
    version="2.0.0",
    description="Backend de agentes com fila asyncio, SQLAlchemy e IA local",
    lifespan=lifespan,
)
app.add_middleware(_CorrelationMiddleware)

app.state.io_fail_target = ""

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------
class AgentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(..., min_length=1, max_length=120)
    role: str = Field(..., min_length=1, max_length=120)
    system_prompt: str = Field(..., min_length=1)
    template_name: Optional[str] = None


class AgentClone(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    new_name: str = Field(..., min_length=1, max_length=120)
    override_role: Optional[str] = None
    override_prompt: Optional[str] = None


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    role: str
    system_prompt: str
    template_name: Optional[str]
    status: str
    cloned_from: Optional[str]
    created_at: datetime
    updated_at: datetime


class AIRequest(BaseModel):
    agent_id: str
    prompt: str
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(512, ge=1, le=4096)


class AIResponse(BaseModel):
    agent_id: str
    response: str
    model: str


class OrchestrateRequest(BaseModel):
    prompt: str = Field(..., min_length=1)


class AnalystOutput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    posicao: str
    tema: str
    descricao: str = Field(alias="descrição")
    principais_beneficios: list[str] = Field(alias="principais_benefícios")
    exemplo_de_uso: Optional[str] = None


class ExecutorOutput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    posicao: str
    tema: str
    descricao: str = Field(alias="descrição")
    acoes_recomendadas: list[str]
    proximo_passo: str


class OrchestratorOutput(BaseModel):
    posicao: str
    tema: str
    resumo_final: str
    recomendacao_final: str
    proximos_passos: list[str]


class OrchestrateResponse(BaseModel):
    user_prompt: str
    analyst_output: AnalystOutput
    executor_output: ExecutorOutput
    orchestrator_output: OrchestratorOutput
    model: str


# ---------------------------------------------------------------------------
# Robô-mãe schemas
# ---------------------------------------------------------------------------
class StepSpecIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action:      str                        = Field(..., min_length=1)
    target_path: Optional[str]              = None
    payload:     Optional[str]              = None
    mode:        Literal["apply", "dry_run"] = "apply"


class RunMissionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mission_id:        str             = Field(..., min_length=1)
    finalizer_id:      str             = Field(..., min_length=1)
    guardian_id:       Optional[str]   = None
    steps:             list[StepSpecIn] = Field(..., min_length=1)
    max_retries:       int             = Field(3, ge=0, le=10)
    retry_delay_secs:  float           = Field(2.0, ge=0.0, le=300.0)
    approval_ttl_secs: int             = Field(86400, ge=60)


class ApprovalDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decided_by: str           = Field(..., min_length=1)
    notes:      Optional[str] = None


# ── Memory Service schemas ───────────────────────────────────────────────────
class MemEventCreate(BaseModel):
    agent_id:    str
    event_type:  str
    summary:     str
    payload:     Optional[dict] = None
    occurred_at: Optional[str]  = None


class MemFactCreate(BaseModel):
    category:   str
    key:        str
    value:      str
    confidence: float         = 1.0
    source:     Optional[str] = None


class MemPatternCreate(BaseModel):
    name:               str
    description:        str
    steps:              list
    trigger_conditions: Optional[list] = None
    success_rate:       float          = 0.0


class MemNodeCreate(BaseModel):
    node_type:  str
    label:      str
    properties: Optional[dict] = None


class MemEdgeCreate(BaseModel):
    source_id:  str
    relation:   str
    target_id:  str
    weight:     float         = 1.0
    properties: Optional[dict] = None


class MemContextRequest(BaseModel):
    agent_id: str


class MemReflectRequest(BaseModel):
    agent_id: str
    intent:   str


class MemReflectRun(BaseModel):
    agent_id: Optional[str] = None   # None → reflexão global


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------
def verify_token(authorization: Optional[str]) -> None:
    if authorization is None or authorization != f"Bearer {API_TOKEN}":
        raise HTTPException(status_code=401, detail="Token inválido ou ausente")


# ---------------------------------------------------------------------------
# DB helpers (sync, called via thread executor or directly)
# ---------------------------------------------------------------------------
def _db_get_agent(agent_id: str) -> AgentRecord:
    with Session() as db:
        rec = db.get(AgentRecord, agent_id)
        if rec is None:
            raise HTTPException(status_code=404, detail=f"Agente {agent_id} não encontrado")
        db.expunge(rec)
        return rec


def _db_save_agent(rec: AgentRecord) -> AgentRecord:
    with Session() as db:
        merged = db.merge(rec)
        db.commit()
        db.refresh(merged)
        db.expunge(merged)
        return merged


def _db_list_agents() -> list[AgentRecord]:
    with Session() as db:
        records = db.query(AgentRecord).order_by(AgentRecord.created_at.desc()).all()
        for r in records:
            db.expunge(r)
        return records


def _db_get_agent_by_name(name: str) -> AgentRecord:
    with Session() as db:
        rec = db.query(AgentRecord).filter(AgentRecord.name == name).order_by(AgentRecord.created_at.desc()).first()
        if rec is None:
            raise HTTPException(status_code=404, detail=f"Agente '{name}' não encontrado")
        db.expunge(rec)
        return rec


# ---------------------------------------------------------------------------
# Core async operations
# ---------------------------------------------------------------------------
async def _async_create_agent(data: AgentCreate) -> AgentRecord:
    loop = asyncio.get_event_loop()
    rec = AgentRecord(
        id=str(uuid.uuid4()),
        name=data.name,
        role=data.role,
        system_prompt=data.system_prompt,
        template_name=data.template_name,
        status=AgentStatus.draft,
    )
    if data.template_name:
        tpl_path = TEMPLATES_DIR / f"{data.template_name}.json"
        if tpl_path.exists():
            tpl = json.loads(tpl_path.read_text())
            rec.role = tpl.get("role", rec.role)
            rec.system_prompt = tpl.get("system_prompt", rec.system_prompt)
            log.info("Template '%s' aplicado ao agente %s", data.template_name, rec.id)
    rec = await loop.run_in_executor(None, _db_save_agent, rec)
    log.info("Agente criado: %s (%s)", rec.name, rec.id)
    return rec


async def _async_clone_agent(agent_id: str, data: AgentClone) -> AgentRecord:
    loop = asyncio.get_event_loop()
    src = await loop.run_in_executor(None, _db_get_agent, agent_id)
    clone = AgentRecord(
        id=str(uuid.uuid4()),
        name=data.new_name,
        role=data.override_role or src.role,
        system_prompt=data.override_prompt or src.system_prompt,
        template_name=src.template_name,
        status=AgentStatus.draft,
        cloned_from=src.id,
    )
    clone = await loop.run_in_executor(None, _db_save_agent, clone)
    log.info("Agente clonado: %s -> %s (%s)", src.id, clone.name, clone.id)
    return clone


async def _async_validate_agent(agent_id: str) -> AgentRecord:
    loop = asyncio.get_event_loop()
    rec = await loop.run_in_executor(None, _db_get_agent, agent_id)
    errors = []
    if not rec.name.strip():
        errors.append("name vazio")
    if not rec.role.strip():
        errors.append("role vazio")
    if len(rec.system_prompt.strip()) < 10:
        errors.append("system_prompt muito curto (mínimo 10 chars)")
    if errors:
        raise HTTPException(status_code=422, detail={"errors": errors})
    rec.status = AgentStatus.validated
    rec.updated_at = datetime.now(timezone.utc)
    await loop.run_in_executor(None, _db_save_agent, rec)
    log.info("Agente validado: %s", agent_id)
    return rec


async def _async_activate_agent(agent_id: str) -> AgentRecord:
    loop = asyncio.get_event_loop()
    rec = await loop.run_in_executor(None, _db_get_agent, agent_id)
    if rec.status not in (AgentStatus.validated, AgentStatus.inactive):
        raise HTTPException(
            status_code=409,
            detail=f"Agente deve estar em status 'validated' ou 'inactive' para ativar (atual: {rec.status})",
        )
    rec.status = AgentStatus.active
    rec.updated_at = datetime.now(timezone.utc)
    await loop.run_in_executor(None, _db_save_agent, rec)
    log.info("Agente ativado: %s", agent_id)
    return rec


async def _async_call_local_ai(agent_id: str, prompt: str, temperature: float, max_tokens: int) -> str:
    loop = asyncio.get_event_loop()
    rec = await loop.run_in_executor(None, _db_get_agent, agent_id)
    if rec.status != AgentStatus.active:
        raise HTTPException(status_code=409, detail=f"Agente não está ativo (status: {rec.status})")
    payload = {
        "model": LOCAL_AI_MODEL,
        "prompt": f"{rec.system_prompt}\n\nUsuário: {prompt}",
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(LOCAL_AI_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", "")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="IA local indisponível (connection refused)")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="IA local não respondeu no prazo")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro na IA local: {exc}")


_ROLE_INSTRUCTIONS: dict[str, str] = {
    "analyst":      "Analise o problema e identifique pontos-chave. Seja objetivo, máximo 3 parágrafos.",
    "executor":     "Com base na análise recebida, proponha ações concretas. Máximo 3 itens.",
    "orchestrator": "Consolide análise e execução em uma conclusão final. Máximo 2 parágrafos.",
    "generic":      "Responda de forma objetiva e concisa, em no máximo 3 parágrafos curtos.",
}

_ANALYST_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "posicao":               {"type": "string"},
        "tema":                  {"type": "string"},
        "descrição":             {"type": "string"},
        "principais_benefícios": {"type": "array", "items": {"type": "string"}},
        "exemplo_de_uso":        {"type": "string"},
    },
    "required": ["posicao", "tema", "descrição", "principais_benefícios"],
    "additionalProperties": False,
}

_EXECUTOR_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "posicao":             {"type": "string"},
        "tema":                {"type": "string"},
        "descrição":           {"type": "string"},
        "acoes_recomendadas":  {"type": "array", "items": {"type": "string"}},
        "proximo_passo":       {"type": "string"},
    },
    "required": ["posicao", "tema", "descrição", "acoes_recomendadas", "proximo_passo"],
    "additionalProperties": False,
}

_ORCHESTRATOR_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "posicao":            {"type": "string"},
        "tema":               {"type": "string"},
        "resumo_final":       {"type": "string"},
        "recomendacao_final": {"type": "string"},
        "proximos_passos":    {"type": "array", "items": {"type": "string"}},
    },
    "required": ["posicao", "tema", "resumo_final", "recomendacao_final", "proximos_passos"],
    "additionalProperties": False,
}

async def _ollama_call(
    system_prompt: str,
    prompt: str,
    role: str = "generic",
    force_json: bool = False,
    model_name: str | None = None,
    json_schema: dict | None = None,
) -> str:
    if force_json:
        instruction = "Responda somente com um objeto JSON válido, compatível com o schema fornecido, sem texto antes ou depois."
    else:
        instruction = _ROLE_INSTRUCTIONS.get(role, _ROLE_INSTRUCTIONS["generic"])
    if model_name is not None:
        resolved_model = model_name
    elif force_json:
        resolved_model = LOCAL_AI_STRUCTURED_MODEL
    else:
        resolved_model = LOCAL_AI_MODEL
    payload: dict = {
        "model": resolved_model,
        "prompt": f"{system_prompt}\n\n{instruction}\n\nUsuário: {prompt}",
        "stream": False,
        "options": {"num_predict": 256},
    }
    if force_json:
        payload["format"] = json_schema if json_schema is not None else "json"
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(LOCAL_AI_URL, json=payload)
            resp.raise_for_status()
            response_text = resp.json().get("response", "")
            if force_json:
                try:
                    json.loads(response_text)
                except ValueError:
                    raise HTTPException(
                        status_code=502,
                        detail="IA local retornou resposta inválida: JSON esperado mas recebeu texto livre",
                    )
            return response_text
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="IA local indisponível (connection refused)")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="IA local não respondeu no prazo")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro na IA local: {exc}")


# ---------------------------------------------------------------------------
# OpenAI Responses API call
# ---------------------------------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL   = os.getenv("OPENAI_MODEL", "")

_OPENAI_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "response": {"type": "string"}
    },
    "required": ["response"],
    "additionalProperties": False,
}

async def _openai_call(
    system_prompt: str,
    prompt: str,
    role: str = "generic",
    force_json: bool = False,
) -> str:
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="Configuração ausente: OPENAI_API_KEY não definida")
    if not OPENAI_MODEL:
        raise HTTPException(status_code=500, detail="Configuração ausente: OPENAI_MODEL não definida")

    from openai import AsyncOpenAI  # lazy import
    instruction = _ROLE_INSTRUCTIONS.get(role, _ROLE_INSTRUCTIONS["generic"])
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    kwargs: dict = {
        "model": OPENAI_MODEL,
        "instructions": f"{system_prompt}\n\n{instruction}",
        "input": prompt,
    }

    if force_json:
        kwargs["text"] = {
            "format": {
                "type": "json_schema",
                "name": "agent_output",
                "schema": _OPENAI_JSON_SCHEMA,
                "strict": True,
            }
        }

    # espaço reservado para reasoning config
    # reasoning_config = os.getenv("OPENAI_REASONING_EFFORT", "")
    # if reasoning_config:
    #     kwargs["reasoning"] = {"effort": reasoning_config}

    try:
        resp = await client.responses.create(**kwargs)
        response_text = resp.output_text
        if force_json:
            try:
                json.loads(response_text)
            except ValueError:
                raise HTTPException(
                    status_code=502,
                    detail="OpenAI retornou resposta inválida: JSON esperado mas recebeu texto livre",
                )
        return response_text
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro na OpenAI: {exc}")


# ---------------------------------------------------------------------------
# Routes — health
# ---------------------------------------------------------------------------
@app.get("/health/live", tags=["health"])
async def health_live():
    return {"status": "live", "ts": datetime.now(timezone.utc).isoformat()}


@app.get("/health/ready", tags=["health"])
async def health_ready():
    try:
        with Session() as db:
            db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    if not db_ok:
        raise HTTPException(status_code=503, detail="Banco de dados indisponível")
    return {"status": "ready", "db": "ok", "ts": datetime.now(timezone.utc).isoformat()}


# ---------------------------------------------------------------------------
# Routes — agents
# ---------------------------------------------------------------------------
@app.get("/agents", tags=["agents"])
async def list_agents():
    loop = asyncio.get_event_loop()
    records = await loop.run_in_executor(None, _db_list_agents)
    return [AgentOut.model_validate(r) for r in records]


@app.post("/agents", status_code=201, tags=["agents"])
async def create_agent(data: AgentCreate, authorization: Optional[str] = Header(default=None)):
    verify_token(authorization)
    rec = await enqueue(_async_create_agent, data)
    return AgentOut.model_validate(rec)


@app.get("/agents/{agent_id}", tags=["agents"])
async def get_agent(agent_id: str):
    loop = asyncio.get_event_loop()
    rec = await loop.run_in_executor(None, _db_get_agent, agent_id)
    return AgentOut.model_validate(rec)


@app.post("/agents/{agent_id}/clone", status_code=201, tags=["agents"])
async def clone_agent(
    agent_id: str,
    data: AgentClone,
    authorization: Optional[str] = Header(default=None),
):
    verify_token(authorization)
    rec = await enqueue(_async_clone_agent, agent_id, data)
    return AgentOut.model_validate(rec)


@app.post("/agents/{agent_id}/validate", tags=["agents"])
async def validate_agent(agent_id: str, authorization: Optional[str] = Header(default=None)):
    verify_token(authorization)
    rec = await enqueue(_async_validate_agent, agent_id)
    return AgentOut.model_validate(rec)


@app.post("/agents/{agent_id}/activate", tags=["agents"])
async def activate_agent(agent_id: str, authorization: Optional[str] = Header(default=None)):
    verify_token(authorization)
    rec = await enqueue(_async_activate_agent, agent_id)
    return AgentOut.model_validate(rec)


# ---------------------------------------------------------------------------
# Routes — AI
# ---------------------------------------------------------------------------
@app.post("/ai/chat", tags=["ai"])
async def ai_chat(req: AIRequest, authorization: Optional[str] = Header(default=None)):
    verify_token(authorization)
    response_text = await enqueue(
        _async_call_local_ai, req.agent_id, req.prompt, req.temperature, req.max_tokens
    )
    return AIResponse(agent_id=req.agent_id, response=response_text, model=LOCAL_AI_MODEL)


# ---------------------------------------------------------------------------
# Routes — orchestrate
# ---------------------------------------------------------------------------
@app.post("/orchestrate", tags=["orchestrate"])
async def orchestrate(req: OrchestrateRequest, authorization: Optional[str] = Header(default=None)):
    verify_token(authorization)
    loop = asyncio.get_event_loop()

    analista = await loop.run_in_executor(None, _db_get_agent_by_name, "robo_analista")
    executor = await loop.run_in_executor(None, _db_get_agent_by_name, "robo_executor")
    orquestrador = await loop.run_in_executor(None, _db_get_agent_by_name, "robo_orquestrador")

    log.info("ORCH_STEP_1_ANALYST_START")
    analyst_prompt = (
        f"Tema: {req.prompt}\n\n"
        f"Faça uma análise factual e explicativa, identificando contexto, pontos-chave e relevância.\n"
        f"No JSON de resposta, preencha 'posicao' com o valor exato: \"analista\".\n"
        f"Preencha 'tema' com o assunto em poucas palavras.\n"
        f"Preencha 'descrição' com a análise em prosa objetiva.\n"
        f"Preencha 'principais_benefícios' com lista de pontos relevantes.\n"
        f"Preencha 'exemplo_de_uso' com um exemplo prático, se aplicável."
    )
    analyst_output = await _ollama_call(
        analista.system_prompt,
        analyst_prompt,
        role="analyst",
        force_json=True,
        json_schema=_ANALYST_SCHEMA,
    )
    log.info("ORCH_STEP_1_ANALYST_DONE")

    log.info("ORCH_STEP_2_EXECUTOR_START")
    executor_prompt = (
        f"Tema: {req.prompt}\n\n"
        f"Com base na análise abaixo, proponha ações práticas e objetivas.\n"
        f"No JSON de resposta, preencha 'posicao' com o valor exato: \"executor\".\n"
        f"Preencha 'tema' com o assunto em poucas palavras.\n"
        f"Preencha 'descrição' com o contexto das ações em prosa curta.\n"
        f"Preencha 'acoes_recomendadas' com lista de ações concretas.\n"
        f"Preencha 'proximo_passo' com a ação mais imediata e prioritária.\n\n"
        f"Análise:\n{analyst_output}"
    )
    executor_output = await _ollama_call(
        executor.system_prompt,
        executor_prompt,
        role="executor",
        force_json=True,
        json_schema=_EXECUTOR_SCHEMA,
    )
    log.info("ORCH_STEP_2_EXECUTOR_DONE")

    log.info("ORCH_STEP_3_ORCHESTRATOR_START")
    orchestrator_prompt = (
        f"Tema: {req.prompt}\n\n"
        f"Consolide a análise e as ações abaixo em uma síntese final objetiva.\n"
        f"No JSON de resposta, preencha 'posicao' com o valor exato: \"orquestrador\".\n"
        f"Preencha 'tema' com o assunto em poucas palavras.\n"
        f"Preencha 'resumo_final' com uma síntese clara em prosa.\n"
        f"Preencha 'recomendacao_final' com a recomendação principal.\n"
        f"Preencha 'proximos_passos' com lista de próximos passos ordenados.\n\n"
        f"Análise:\n{analyst_output}\n\n"
        f"Ações propostas:\n{executor_output}"
    )
    orchestrator_output = await _ollama_call(
        orquestrador.system_prompt,
        orchestrator_prompt,
        role="orchestrator",
        force_json=True,
        json_schema=_ORCHESTRATOR_SCHEMA,
    )
    log.info("ORCH_STEP_3_ORCHESTRATOR_DONE")

    def _parse_typed(label: str, text: str, model_cls):
        try:
            data = json.loads(text)
        except ValueError:
            raise HTTPException(
                status_code=502,
                detail=f"Parse JSON falhou em {label}: resposta inválida do modelo",
            )
        try:
            return model_cls(**data)
        except Exception as e:
            raise HTTPException(
                status_code=502,
                detail=f"Validação Pydantic falhou em {label}: {e}",
            )

    return OrchestrateResponse(
        user_prompt=req.prompt,
        analyst_output=_parse_typed("analyst_output", analyst_output, AnalystOutput),
        executor_output=_parse_typed("executor_output", executor_output, ExecutorOutput),
        orchestrator_output=_parse_typed("orchestrator_output", orchestrator_output, OrchestratorOutput),
        model=LOCAL_AI_STRUCTURED_MODEL,
    )


# ---------------------------------------------------------------------------
# Routes — queue status
# ---------------------------------------------------------------------------
@app.get("/queue/status", tags=["queue"])
async def queue_status():
    return {"pending": task_queue.qsize()}


# ---------------------------------------------------------------------------
# Agente 2 — Finalizador / Executor Controlado
# ---------------------------------------------------------------------------

# -- 1. Schemas Pydantic -----------------------------------------------------

class FinalizerMode(str, Enum):
    plan    = "plan"
    dry_run = "dry_run"
    apply   = "apply"


class FinalizerManifestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allowed_actions:   list[str] = Field(default_factory=list)
    allowed_paths:     list[str] = Field(default_factory=list)
    forbidden_paths:   list[str] = Field(default_factory=list)
    allowed_hosts:     list[str] = Field(default_factory=list)
    requires_approval: list[str] = Field(default_factory=list)


class FinalizerManifestOut(FinalizerManifestIn):
    id:         str
    agent_id:   str
    created_at: datetime


class CreateFinalizerAgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name:     str
    manifest: Optional[FinalizerManifestIn] = None


class FinalizerExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode:        FinalizerMode
    action:      str
    target_path: Optional[str] = None
    payload:     Optional[str] = None
    guardian_id: Optional[str] = None


class FinalizerExecuteResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_id:    str
    audit_id:    str
    mode:        str
    action:      str
    status:      str
    snapshot_id: Optional[str]  = None
    applied:     bool           = False
    reason:      Optional[str]  = None
    evidence:    Optional[dict] = None
    ts:          str


# -- 2. DB helpers ------------------------------------------------------------

def _db_save_manifest(agent_id: str, m: FinalizerManifestIn) -> FinalizerManifestRecord:
    with Session() as s:
        existing = s.query(FinalizerManifestRecord).filter_by(agent_id=agent_id).first()
        if existing:
            existing.allowed_actions   = json.dumps(m.allowed_actions)
            existing.allowed_paths     = json.dumps(m.allowed_paths)
            existing.forbidden_paths   = json.dumps(m.forbidden_paths)
            existing.allowed_hosts     = json.dumps(m.allowed_hosts)
            existing.requires_approval = json.dumps(m.requires_approval)
            s.commit()
            s.refresh(existing)
            return existing
        rec = FinalizerManifestRecord(
            agent_id          = agent_id,
            allowed_actions   = json.dumps(m.allowed_actions),
            allowed_paths     = json.dumps(m.allowed_paths),
            forbidden_paths   = json.dumps(m.forbidden_paths),
            allowed_hosts     = json.dumps(m.allowed_hosts),
            requires_approval = json.dumps(m.requires_approval),
        )
        s.add(rec)
        s.commit()
        s.refresh(rec)
        return rec


def _db_get_manifest(agent_id: str) -> Optional[FinalizerManifestRecord]:
    with Session() as s:
        return s.query(FinalizerManifestRecord).filter_by(agent_id=agent_id).first()


def _db_save_snapshot(agent_id: str, path: str, content_before: Optional[str]) -> FinalizerSnapshotRecord:
    with Session() as s:
        rec = FinalizerSnapshotRecord(
            agent_id       = agent_id,
            path           = path,
            content_before = content_before,
        )
        s.add(rec)
        s.commit()
        s.refresh(rec)
        return rec


def _db_get_snapshot(snapshot_id: str) -> Optional[FinalizerSnapshotRecord]:
    with Session() as s:
        return s.query(FinalizerSnapshotRecord).filter_by(id=snapshot_id).first()


def _db_save_audit(rec: FinalizerAuditRecord) -> FinalizerAuditRecord:
    with Session() as s:
        s.add(rec)
        s.commit()
        s.refresh(rec)
        return rec


def _db_list_audit(agent_id: str) -> list[dict]:
    with Session() as s:
        rows = (
            s.query(FinalizerAuditRecord)
            .filter_by(agent_id=agent_id)
            .order_by(FinalizerAuditRecord.ts.desc())
            .limit(100)
            .all()
        )
        return [
            {
                "id":      r.id,
                "action":  r.action,
                "mode":    r.mode,
                "status":  r.status,
                "details": json.loads(r.details),
                "ts":      r.ts.isoformat(),
            }
            for r in rows
        ]


# -- 3. Matriz de ações + core helpers ----------------------------------------

# Ações com implementação real neste servidor
_FINALIZER_IMPLEMENTED: frozenset[str] = frozenset({"write_file", "read_file", "list_dir"})

# Hardcoded — SEMPRE exigem aprovação humana (não pode ser sobrescrito pelo manifesto)
_FINALIZER_ALWAYS_NEEDS_APPROVAL: frozenset[str] = frozenset(
    {"run_script", "git_push", "delete_file", "access_secret", "edit_core"}
)

# Hardcoded — SEMPRE proibidas (não pode ser sobrescrito pelo manifesto)
_FINALIZER_ALWAYS_FORBIDDEN: frozenset[str] = frozenset(
    {"modify_manifest", "alter_permissions", "install_package"}
)

_DEFAULT_FINALIZER_MANIFEST = FinalizerManifestIn(
    allowed_actions   = ["write_file", "read_file", "list_dir"],
    allowed_paths     = ["agents/", "scripts/", "templates/", "tests/"],
    forbidden_paths   = [
        "app/", "jod_brain/", ".env", "main_fase2.py",
        "jod_brain_main.py", "requirements.txt", "Dockerfile",
        "templates/finalizer_manifest.json",
    ],
    allowed_hosts     = [],
    requires_approval = ["run_script", "git_push", "delete_file", "access_secret", "edit_core"],
)


def _manifest_from_record(rec: FinalizerManifestRecord) -> FinalizerManifestIn:
    return FinalizerManifestIn(
        allowed_actions   = json.loads(rec.allowed_actions),
        allowed_paths     = json.loads(rec.allowed_paths),
        forbidden_paths   = json.loads(rec.forbidden_paths),
        allowed_hosts     = json.loads(rec.allowed_hosts),
        requires_approval = json.loads(rec.requires_approval),
    )


def _manifest_to_out(rec: FinalizerManifestRecord) -> FinalizerManifestOut:
    return FinalizerManifestOut(
        id                = rec.id,
        agent_id          = rec.agent_id,
        created_at        = rec.created_at,
        allowed_actions   = json.loads(rec.allowed_actions),
        allowed_paths     = json.loads(rec.allowed_paths),
        forbidden_paths   = json.loads(rec.forbidden_paths),
        allowed_hosts     = json.loads(rec.allowed_hosts),
        requires_approval = json.loads(rec.requires_approval),
    )


def _check_path_allowed(path: str, manifest: FinalizerManifestIn) -> tuple[bool, str]:
    """
    Retorna (True, "") se o path é permitido, ou (False, motivo) caso contrário.
    Previne path traversal via canonicalização com Path.resolve().
    """
    if not path:
        return False, "path vazio"

    p = Path(path)

    # Rejeita paths absolutos
    if p.is_absolute():
        return False, "path absoluto não permitido"

    # Rejeita componentes de traversal
    if ".." in p.parts:
        return False, "path traversal (..) não permitido"

    # Canonicaliza em relação a BASE_DIR
    try:
        resolved = (BASE_DIR / p).resolve()
        resolved.relative_to(BASE_DIR)  # lança ValueError se sair de BASE_DIR
    except ValueError:
        return False, "path fora de BASE_DIR"

    rel = str(resolved.relative_to(BASE_DIR))

    # Verifica forbidden_paths
    for fp in manifest.forbidden_paths:
        fp_norm = fp.rstrip("/")
        if rel == fp_norm or rel.startswith(fp_norm + "/") or rel.startswith(fp_norm + os.sep):
            return False, f"path em forbidden_paths: {fp}"

    # Verifica allowed_paths
    for ap in manifest.allowed_paths:
        ap_norm = ap.rstrip("/")
        if rel == ap_norm or rel.startswith(ap_norm + "/") or rel.startswith(ap_norm + os.sep):
            return True, ""

    return False, "path fora de allowed_paths"


def _build_audit(agent_id: str, action: str, mode: str, status: str, **kw) -> FinalizerAuditRecord:
    return FinalizerAuditRecord(
        agent_id = agent_id,
        action   = action,
        mode     = mode,
        status   = status,
        details  = json.dumps(kw),
    )


# -- 4. Async operations ------------------------------------------------------

async def _async_create_finalizer_agent(req: CreateFinalizerAgentRequest) -> dict:
    tpl_path = TEMPLATES_DIR / "finalizer_agent.json"
    if not tpl_path.exists():
        raise HTTPException(status_code=500, detail="Template finalizer_agent.json não encontrado")

    tpl = json.loads(tpl_path.read_text(encoding="utf-8"))

    with Session() as s:
        agent = AgentRecord(
            name          = req.name,
            role          = tpl.get("role", "finalizador"),
            system_prompt = tpl.get("system_prompt", ""),
            template_name = "finalizer_agent",
            status        = AgentStatus.draft,
        )
        s.add(agent)
        s.commit()
        s.refresh(agent)
        agent_id = agent.id

    manifest_in = req.manifest or _DEFAULT_FINALIZER_MANIFEST
    _db_save_manifest(agent_id, manifest_in)

    _db_save_audit(_build_audit(agent_id, "create_finalizer_agent", "apply", "created",
                                name=req.name, manifest_used=req.manifest is not None))

    return {"agent_id": agent_id, "status": AgentStatus.draft, "name": req.name}


async def _async_validate_finalizer(agent_id: str) -> dict:
    with Session() as s:
        agent = s.query(AgentRecord).filter_by(id=agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agente não encontrado")
        if agent.status != AgentStatus.draft:
            raise HTTPException(status_code=409, detail=f"Agente já está em status '{agent.status}'")

    manifest_rec = _db_get_manifest(agent_id)
    if not manifest_rec:
        raise HTTPException(status_code=422, detail="Manifesto não encontrado — não é possível validar")

    manifest = _manifest_from_record(manifest_rec)
    errors: list[str] = []

    if not manifest.allowed_actions:
        errors.append("allowed_actions vazio")
    if not manifest.allowed_paths:
        errors.append("allowed_paths vazio")

    if errors:
        _db_save_audit(_build_audit(agent_id, "validate", "apply", "validation_failed", errors=errors))
        raise HTTPException(status_code=422, detail={"errors": errors})

    with Session() as s:
        agent = s.query(AgentRecord).filter_by(id=agent_id).first()
        agent.status = AgentStatus.validated
        s.commit()

    _db_save_audit(_build_audit(agent_id, "validate", "apply", "validated"))
    return {"agent_id": agent_id, "status": AgentStatus.validated}


async def _async_activate_finalizer(agent_id: str) -> dict:
    if not _db_get_manifest(agent_id):
        raise HTTPException(status_code=422, detail="Manifesto ausente — ativação negada")

    rec = await _async_activate_agent(agent_id)
    _db_save_audit(_build_audit(agent_id, "activate", "apply", "activated"))
    return {"agent_id": agent_id, "status": rec.status}


async def _async_finalizer_execute(agent_id: str, req: FinalizerExecuteRequest) -> FinalizerExecuteResult:
    # Carrega agente
    with Session() as s:
        agent = s.query(AgentRecord).filter_by(id=agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agente não encontrado")
        if agent.status != AgentStatus.active:
            raise HTTPException(status_code=409, detail=f"Agente não está ativo (status: '{agent.status}')")

    manifest_rec = _db_get_manifest(agent_id)
    if not manifest_rec:
        raise HTTPException(status_code=422, detail="Manifesto ausente")

    manifest = _manifest_from_record(manifest_rec)
    action   = req.action
    mode     = req.mode

    ts             = datetime.now(timezone.utc).isoformat()
    transaction_id = str(uuid.uuid4())

    # Modo plan — apenas descreve, sem executar nada
    if mode == FinalizerMode.plan:
        audit = _db_save_audit(_build_audit(agent_id, action, mode, "planned", target_path=req.target_path))
        return FinalizerExecuteResult(
            agent_id=agent_id, audit_id=audit.id, mode=mode, action=action,
            status="planned", applied=False,
            reason="Modo plan: nenhuma ação executada", ts=ts,
        )

    # ── REGRA 1: Ações hardcoded SEMPRE proibidas ─────────────────────────────
    if action in _FINALIZER_ALWAYS_FORBIDDEN:
        audit = _db_save_audit(_build_audit(agent_id, action, mode, "forbidden",
                                            reason="hardcoded forbidden", action_name=action))
        return FinalizerExecuteResult(
            agent_id=agent_id, audit_id=audit.id, mode=mode, action=action,
            status="forbidden", applied=False,
            reason=f"Ação '{action}' é hardcoded forbidden e não pode ser executada",
            ts=ts,
        )

    # ── REGRA 2: Ações hardcoded SEMPRE exigem aprovação ──────────────────────
    if action in _FINALIZER_ALWAYS_NEEDS_APPROVAL:
        audit = _db_save_audit(_build_audit(agent_id, action, mode, "needs_approval",
                                            reason="hardcoded needs_approval", action_name=action))
        return FinalizerExecuteResult(
            agent_id=agent_id, audit_id=audit.id, mode=mode, action=action,
            status="needs_approval", applied=False,
            reason=f"Ação '{action}' exige aprovação humana explícita (hardcoded)",
            ts=ts,
        )

    # ── REGRA 3: Manifesto requires_approval ──────────────────────────────────
    if action in manifest.requires_approval:
        audit = _db_save_audit(_build_audit(agent_id, action, mode, "needs_approval",
                                            reason="manifest requires_approval", action_name=action))
        return FinalizerExecuteResult(
            agent_id=agent_id, audit_id=audit.id, mode=mode, action=action,
            status="needs_approval", applied=False,
            reason=f"Ação '{action}' exige aprovação pelo manifesto",
            ts=ts,
        )

    # ── REGRA 4: Ação não está em allowed_actions do manifesto ────────────────
    if action not in manifest.allowed_actions:
        audit = _db_save_audit(_build_audit(agent_id, action, mode, "forbidden",
                                            reason="not in allowed_actions", action_name=action))
        return FinalizerExecuteResult(
            agent_id=agent_id, audit_id=audit.id, mode=mode, action=action,
            status="forbidden", applied=False,
            reason=f"Ação '{action}' não está em allowed_actions do manifesto",
            ts=ts,
        )

    # ── REGRA 5: Validação de path ────────────────────────────────────────────
    if req.target_path is not None:
        ok, reason = _check_path_allowed(req.target_path, manifest)
        if not ok:
            audit = _db_save_audit(_build_audit(agent_id, action, mode, "forbidden",
                                                reason=reason, target_path=req.target_path))
            return FinalizerExecuteResult(
                agent_id=agent_id, audit_id=audit.id, mode=mode, action=action,
                status="forbidden", applied=False, reason=reason, ts=ts,
            )

    # ── REGRA 6: Ação não implementada ───────────────────────────────────────
    if action not in _FINALIZER_IMPLEMENTED:
        audit = _db_save_audit(_build_audit(agent_id, action, mode, "not_implemented", action_name=action))
        raise HTTPException(
            status_code=501,
            detail=f"Ação '{action}' passou nas políticas mas não tem implementação neste servidor",
        )

    # ── Execução real ─────────────────────────────────────────────────────────
    snapshot_id: Optional[str] = None
    evidence:    Optional[dict] = None
    applied = False
    status = "dry_run_ok" if mode == FinalizerMode.dry_run else "applied"

    if action == "read_file":
        if not req.target_path:
            raise HTTPException(status_code=400, detail="target_path obrigatório para read_file")
        abs_path = (BASE_DIR / req.target_path).resolve()
        if mode in (FinalizerMode.dry_run, FinalizerMode.apply):
            if abs_path.is_file():
                raw = abs_path.read_text(encoding="utf-8", errors="replace")
                evidence = {
                    "path":            req.target_path,
                    "size_bytes":      abs_path.stat().st_size,
                    "content_preview": raw[:2000],
                }
            else:
                evidence = {"path": req.target_path, "exists": False}
        applied = mode == FinalizerMode.apply

    elif action == "list_dir":
        if not req.target_path:
            raise HTTPException(status_code=400, detail="target_path obrigatório para list_dir")
        abs_path = (BASE_DIR / req.target_path).resolve()
        if mode in (FinalizerMode.dry_run, FinalizerMode.apply):
            if abs_path.is_dir():
                entries = [e.name for e in sorted(abs_path.iterdir())]
                evidence = {
                    "path":    req.target_path,
                    "entries": entries,
                    "count":   len(entries),
                }
            else:
                evidence = {"path": req.target_path, "is_dir": False}
        applied = mode == FinalizerMode.apply

    elif action == "write_file":
        if not req.target_path:
            raise HTTPException(status_code=400, detail="target_path obrigatório para write_file")
        abs_path = (BASE_DIR / req.target_path).resolve()

        # Snapshot do conteúdo anterior (se existir)
        content_before: Optional[str] = None
        if abs_path.is_file():
            content_before = abs_path.read_text(encoding="utf-8", errors="replace")

        snap = _db_save_snapshot(agent_id, req.target_path, content_before)
        snapshot_id = snap.id

        if mode == FinalizerMode.apply:
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            if req.guardian_id:
                attest = await _guardian_attest(
                    guardian_id    = req.guardian_id,
                    finalizer_id   = agent_id,
                    action         = action,
                    transaction_id = transaction_id,
                    target_path    = req.target_path,
                )
                # ── VETO ──────────────────────────────────────────────────
                # shadow nunca criado; write nunca ocorre
                if attest["guardian_status"] != "approved":
                    _db_save_audit(_build_audit(
                        agent_id, action, mode, "forbidden",
                        reason      = "guardian_veto:" + attest["guardian_status"],
                        target_path = req.target_path,
                        applied     = False,
                        snapshot_id = snapshot_id,
                        evidence    = {
                            "guardian_transaction_id": transaction_id,
                            "guardian_status":         attest["guardian_status"],
                        },
                    ))
                    raise HTTPException(
                        status_code=403,
                        detail={
                            "guardian_status":         attest["guardian_status"],
                            "guardian_transaction_id": transaction_id,
                            "reason": (
                                f"Guardião vetou a ação '{action}' "
                                f"(status: '{attest['guardian_status']}')"
                            ),
                            "target_path": req.target_path,
                        },
                    )
                # ── FIM VETO — só chega aqui se guardian_status == "approved"
            # ── shadow + escrita atômica (guardian aprovado ou guardian ausente) ──
            shadow_path = abs_path.parent / f".{abs_path.name}.{transaction_id}.jod_tmp"
            _int_audit_id = attest["integration_audit_id"] if req.guardian_id else None

            try:
                encoded = (req.payload or "").encode("utf-8")

                with open(shadow_path, "wb") as fh:
                    fh.write(encoded)
                    fh.flush()
                    os.fsync(fh.fileno())

                # Hook de teste:
                # dispara DENTRO do try, DEPOIS de fsync e ANTES de os.replace.
                # Isso força o except real: cleanup de shadow + mark_io_failed + re-raise.
                if (
                    os.environ.get("JOD_ENV") == "test"
                    and app.state.io_fail_target == req.target_path
                ):
                    raise OSError(f"[test hook] falha forçada em '{req.target_path}'")

                os.replace(shadow_path, abs_path)

                if _int_audit_id:
                    _db_mark_io_committed(_int_audit_id)

            except Exception as _io_err:
                if shadow_path.exists():
                    shadow_path.unlink(missing_ok=True)

                if _int_audit_id:
                    _db_mark_io_failed(_int_audit_id, reason=str(_io_err))

                raise

            applied = True
            evidence = {
                "path": req.target_path,
                "bytes_written": len((req.payload or "").encode()),
            }
            if req.guardian_id:
                evidence["guardian_transaction_id"] = transaction_id
        else:
            # dry_run: snapshot criado mas arquivo não alterado
            evidence = {
                "path":        req.target_path,
                "would_write": len((req.payload or "").encode()),
                "snapshot_id": snapshot_id,
            }

    audit = _db_save_audit(_build_audit(
        agent_id, action, mode, status,
        target_path=req.target_path, applied=applied,
        snapshot_id=snapshot_id, evidence=evidence,
    ))
    return FinalizerExecuteResult(
        agent_id=agent_id, audit_id=audit.id, mode=mode, action=action,
        status=status, snapshot_id=snapshot_id, applied=applied,
        evidence=evidence, ts=ts,
    )


async def _async_finalizer_rollback(agent_id: str, snapshot_id: str) -> dict:
    snap = _db_get_snapshot(snapshot_id)
    if not snap:
        raise HTTPException(status_code=404, detail="Snapshot não encontrado")
    if snap.agent_id != agent_id:
        raise HTTPException(status_code=403, detail="Snapshot não pertence a este agente")
    if snap.rolled_back:
        raise HTTPException(status_code=409, detail="Snapshot já foi revertido")

    manifest_rec = _db_get_manifest(agent_id)
    if not manifest_rec:
        raise HTTPException(status_code=422, detail="Manifesto ausente — rollback negado")

    manifest = _manifest_from_record(manifest_rec)
    ok, reason = _check_path_allowed(snap.path, manifest)
    if not ok:
        raise HTTPException(status_code=403, detail=f"Rollback negado: {reason}")

    abs_path = (BASE_DIR / snap.path).resolve()

    if snap.content_before is None:
        if abs_path.exists():
            abs_path.unlink()
        msg = "arquivo removido (não existia antes do snapshot)"
    else:
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(snap.content_before, encoding="utf-8")
        msg = f"conteúdo restaurado ({len(snap.content_before)} bytes)"

    with Session() as s:
        rec = s.query(FinalizerSnapshotRecord).filter_by(id=snapshot_id).first()
        rec.rolled_back = True
        s.commit()

    _db_save_audit(_build_audit(agent_id, "rollback", "apply", "rolled_back",
                                snapshot_id=snapshot_id, path=snap.path, msg=msg))

    return {"agent_id": agent_id, "snapshot_id": snapshot_id, "rolled_back": True, "msg": msg}


# -- 5. Routes — Agente 2 Finalizador ----------------------------------------

@app.post("/agents/finalizer", tags=["finalizer"])
async def create_finalizer_agent(req: CreateFinalizerAgentRequest,
                                 authorization: Optional[str] = Header(default=None)):
    verify_token(authorization)
    return await _async_create_finalizer_agent(req)


@app.get("/agents/{agent_id}/finalizer/manifest", tags=["finalizer"],
         response_model=FinalizerManifestOut)
async def get_finalizer_manifest(agent_id: str):
    rec = _db_get_manifest(agent_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Manifesto não encontrado")
    return _manifest_to_out(rec)


@app.post("/agents/{agent_id}/finalizer/validate", tags=["finalizer"])
async def validate_finalizer_agent(agent_id: str,
                                   authorization: Optional[str] = Header(default=None)):
    verify_token(authorization)
    return await _async_validate_finalizer(agent_id)


@app.post("/agents/{agent_id}/finalizer/activate", tags=["finalizer"])
async def activate_finalizer_agent(agent_id: str,
                                   authorization: Optional[str] = Header(default=None)):
    verify_token(authorization)
    return await _async_activate_finalizer(agent_id)


@app.post("/agents/{agent_id}/finalizer/execute", tags=["finalizer"],
          response_model=FinalizerExecuteResult)
async def execute_finalizer(agent_id: str, req: FinalizerExecuteRequest,
                            authorization: Optional[str] = Header(default=None)):
    verify_token(authorization)
    return await _async_finalizer_execute(agent_id, req)


@app.post("/agents/{agent_id}/finalizer/rollback/{snapshot_id}", tags=["finalizer"])
async def rollback_finalizer(agent_id: str, snapshot_id: str,
                              authorization: Optional[str] = Header(default=None)):
    verify_token(authorization)
    return await _async_finalizer_rollback(agent_id, snapshot_id)


@app.get("/agents/{agent_id}/finalizer/audit", tags=["finalizer"])
async def list_finalizer_audit(agent_id: str,
                               authorization: Optional[str] = Header(default=None)):
    verify_token(authorization)
    return {"agent_id": agent_id, "audit": _db_list_audit(agent_id)}


# ---------------------------------------------------------------------------
# Agente 3 — Guardião / Auditor / Validador
# ---------------------------------------------------------------------------

# -- 1. Schemas Pydantic -----------------------------------------------------

class CreateGuardianAgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str


class GuardianCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str


class GuardianCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_id:  str
    audit_id:  str
    action:    str
    status:    str
    ts:        str


# -- 2. DB helpers ------------------------------------------------------------

def _build_guardian_audit(agent_id: str, action: str, status: str, **kw) -> GuardianAuditRecord:
    return GuardianAuditRecord(
        agent_id = agent_id,
        action   = action,
        status   = status,
        details  = json.dumps(kw),
    )


def _db_save_guardian_audit(rec: GuardianAuditRecord) -> GuardianAuditRecord:
    with Session() as s:
        s.add(rec)
        s.commit()
        s.refresh(rec)
        return rec


def _db_list_guardian_audit(agent_id: str) -> list[dict]:
    with Session() as s:
        rows = (
            s.query(GuardianAuditRecord)
            .filter_by(agent_id=agent_id)
            .order_by(GuardianAuditRecord.ts.desc())
            .limit(100)
            .all()
        )
        return [
            {
                "id":      r.id,
                "action":  r.action,
                "status":  r.status,
                "details": json.loads(r.details),
                "ts":      r.ts.isoformat(),
            }
            for r in rows
        ]


# -- 3. Política hardcoded ---------------------------------------------------

_GUARDIAN_ALWAYS_BLOCKED: frozenset[str] = frozenset(
    {"modify_manifest", "alter_permissions", "install_package"}
)

_GUARDIAN_ALWAYS_NEEDS_APPROVAL: frozenset[str] = frozenset(
    {"run_script", "git_push", "delete_file", "access_secret", "edit_core"}
)


def _apply_guardian_policy(action: str, target_path: Optional[str] = None) -> tuple[str, str]:
    """Avalia política hardcoded do Guardião. Retorna (status, reason) sem persistir."""
    if action in _GUARDIAN_ALWAYS_BLOCKED:
        return "blocked", "hardcoded blocked"
    if action in _GUARDIAN_ALWAYS_NEEDS_APPROVAL:
        return "needs_approval", "hardcoded needs_approval"
    if action == "write_file" and target_path:
        if target_path.startswith("restricted/"):
            return "blocked", "path em zona restrita (restricted/)"
        if target_path.startswith("pending/"):
            return "needs_approval", "path em zona pendente (pending/)"
    return "approved", ""


# ---------------------------------------------------------------------------
# Integração — Finalizador + Guardião
# ---------------------------------------------------------------------------

def _build_integration_audit(
    finalizer_id:    str,
    guardian_id:     str,
    action:          str,
    guardian_status: str,
    transaction_id:  str,
    target_path:     Optional[str] = None,
) -> IntegrationAuditRecord:
    return IntegrationAuditRecord(
        finalizer_id    = finalizer_id,
        guardian_id     = guardian_id,
        action          = action,
        target_path     = target_path,
        transaction_id  = transaction_id,
        guardian_status = guardian_status,
    )


def _db_save_integration_audit(rec: IntegrationAuditRecord) -> IntegrationAuditRecord:
    with Session() as s:
        s.add(rec)
        s.commit()
        s.refresh(rec)
        return rec


def _db_mark_io_committed(integration_audit_id: str) -> None:
    """Confirma commit físico real após os.replace() bem-sucedido."""
    with Session() as s:
        rec = s.query(IntegrationAuditRecord).filter_by(id=integration_audit_id).first()
        if rec:
            rec.io_committed = True
            rec.io_failure_reason = None
            rec.io_finalized_at = datetime.now(timezone.utc)
            s.commit()


def _db_mark_io_failed(integration_audit_id: str, reason: str) -> None:
    """Registra falha de I/O. Mantém trilha honesta."""
    with Session() as s:
        rec = s.query(IntegrationAuditRecord).filter_by(id=integration_audit_id).first()
        if rec:
            rec.io_committed = False
            rec.io_failure_reason = reason[:512]
            rec.io_finalized_at = datetime.now(timezone.utc)
            s.commit()


async def _guardian_attest(
    guardian_id:    str,
    finalizer_id:   str,
    action:         str,
    transaction_id: str,
    target_path:    Optional[str] = None,
) -> dict:
    """Avalia ação via política do Guardião.
    404 se Guardião não existe. 409 se não está ativo.
    Persiste em integration_audit e gera trilha cruzada em guardian_audit
    com o mesmo transaction_id antes de retornar.
    Retorna {"guardian_status": ..., "integration_audit_id": ...} para que
    o chamador decida se veta."""
    with Session() as s:
        agent = s.query(AgentRecord).filter_by(id=guardian_id).first()
        if not agent:
            raise HTTPException(
                status_code=404,
                detail=f"Guardião '{guardian_id}' não encontrado",
            )
        if agent.status != AgentStatus.active:
            raise HTTPException(
                status_code=409,
                detail=f"Guardião não está ativo (status: '{agent.status}')",
            )

    status, _reason = _apply_guardian_policy(action, target_path=target_path)

    # 1. Persiste em integration_audit (antes de qualquer escrita no fs)
    int_rec = _db_save_integration_audit(
        _build_integration_audit(
            finalizer_id    = finalizer_id,
            guardian_id     = guardian_id,
            action          = action,
            guardian_status = status,
            transaction_id  = transaction_id,
            target_path     = target_path,
        )
    )

    # 2. Trilha cruzada em guardian_audit com o mesmo transaction_id
    _db_save_guardian_audit(
        _build_guardian_audit(
            guardian_id, action, f"attested:{status}",
            transaction_id       = transaction_id,
            finalizer_id         = finalizer_id,
            integration_audit_id = int_rec.id,
        )
    )

    return {"guardian_status": status, "integration_audit_id": int_rec.id}


# -- 4. Async operations -----------------------------------------------------

async def _async_create_guardian_agent(req: CreateGuardianAgentRequest) -> dict:
    tpl_path = TEMPLATES_DIR / "guardian_agent.json"
    if not tpl_path.exists():
        raise HTTPException(status_code=500, detail="Template guardian_agent.json não encontrado")

    tpl = json.loads(tpl_path.read_text(encoding="utf-8"))

    with Session() as s:
        agent = AgentRecord(
            name          = req.name,
            role          = tpl.get("role", "guardiao"),
            system_prompt = tpl.get("system_prompt", ""),
            template_name = "guardian_agent",
            status        = AgentStatus.draft,
        )
        s.add(agent)
        s.commit()
        s.refresh(agent)
        agent_id = agent.id

    _db_save_guardian_audit(_build_guardian_audit(agent_id, "create_guardian_agent", "created",
                                                   name=req.name))
    return {"agent_id": agent_id, "status": AgentStatus.draft, "name": req.name}


async def _async_validate_guardian(agent_id: str) -> dict:
    with Session() as s:
        agent = s.query(AgentRecord).filter_by(id=agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agente não encontrado")
        if agent.status != AgentStatus.draft:
            raise HTTPException(status_code=409, detail=f"Agente já está em status '{agent.status}'")

    with Session() as s:
        agent = s.query(AgentRecord).filter_by(id=agent_id).first()
        agent.status = AgentStatus.validated
        s.commit()

    _db_save_guardian_audit(_build_guardian_audit(agent_id, "validate", "validated"))
    return {"agent_id": agent_id, "status": AgentStatus.validated}


async def _async_activate_guardian(agent_id: str) -> dict:
    rec = await _async_activate_agent(agent_id)
    _db_save_guardian_audit(_build_guardian_audit(agent_id, "activate", "activated"))
    return {"agent_id": agent_id, "status": rec.status}


async def _async_guardian_check(agent_id: str, req: GuardianCheckRequest) -> GuardianCheckResult:
    with Session() as s:
        agent = s.query(AgentRecord).filter_by(id=agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agente não encontrado")
        if agent.status != AgentStatus.active:
            raise HTTPException(status_code=409,
                                detail=f"Agente não está ativo (status: '{agent.status}')")

    action = req.action
    ts     = datetime.now(timezone.utc).isoformat()

    status, reason = _apply_guardian_policy(action)
    kw = {"reason": reason} if reason else {}
    rec = _db_save_guardian_audit(_build_guardian_audit(agent_id, action, status, **kw))
    return GuardianCheckResult(
        agent_id=agent_id, audit_id=rec.id, action=action, status=status, ts=ts
    )


# -- 5. Routes — Agente 3 Guardião -------------------------------------------

@app.post("/agents/guardian", tags=["guardian"])
async def create_guardian_agent(req: CreateGuardianAgentRequest,
                                authorization: Optional[str] = Header(default=None)):
    verify_token(authorization)
    return await _async_create_guardian_agent(req)


@app.post("/agents/{agent_id}/guardian/validate", tags=["guardian"])
async def validate_guardian_agent(agent_id: str,
                                  authorization: Optional[str] = Header(default=None)):
    verify_token(authorization)
    return await _async_validate_guardian(agent_id)


@app.post("/agents/{agent_id}/guardian/activate", tags=["guardian"])
async def activate_guardian_agent(agent_id: str,
                                  authorization: Optional[str] = Header(default=None)):
    verify_token(authorization)
    return await _async_activate_guardian(agent_id)


@app.post("/agents/{agent_id}/guardian/check", tags=["guardian"],
          response_model=GuardianCheckResult)
async def check_guardian(agent_id: str, req: GuardianCheckRequest,
                         authorization: Optional[str] = Header(default=None)):
    verify_token(authorization)
    return await _async_guardian_check(agent_id, req)


@app.get("/agents/{agent_id}/guardian/audit", tags=["guardian"])
async def list_guardian_audit(agent_id: str,
                              authorization: Optional[str] = Header(default=None)):
    verify_token(authorization)
    return {"agent_id": agent_id, "audit": _db_list_guardian_audit(agent_id)}


# ---------------------------------------------------------------------------
# Test routes (only when JOD_ENV=test)
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Robô-mãe — MVP
# ---------------------------------------------------------------------------
from robo_mae.context         import MissionContext, StepSpec
from robo_mae.executor        import MissionExecutor
from robo_mae.mission_control import MissionControl as _MissionControl
from robo_mae.registry        import AgentRegistry
from robo_mae.reporter        import get_mission_summary
from robo_mae.watchdog        import WatchdogScanner

# ---------------------------------------------------------------------------
# Memory Service
# ---------------------------------------------------------------------------
from memory_service.migrate            import _migrate_memory_service
from memory_service.storage            import (
    insert_episodic_event, list_episodic_events,
    upsert_semantic_fact, list_semantic_facts,
    upsert_procedural_pattern, list_procedural_patterns,
    insert_graph_node, insert_graph_edge, list_graph_neighbors,
)
from memory_service.retrieval_gateway  import RetrievalGateway
from memory_service.policy_guard       import assert_advisory_only, MemoryGovernanceError
from memory_service.reflection_engine  import run_reflection


async def _redispatch_mission(mission_id: str) -> None:
    """
    Redespacho formal de missão pelo watchdog.
    Lê context_json de mission_control, reconstrói MissionContext e executa
    pelo caminho normal (claim/takeover/fencing preservados).
    Não executa inline dentro do watchdog.
    """
    with Session() as s:
        row = s.execute(
            text("SELECT context_json FROM mission_control WHERE mission_id=:mid"),
            {"mid": mission_id},
        ).fetchone()

    if row is None or not row[0]:
        log.error("redispatch: context_json ausente para mission=%s", mission_id)
        return

    try:
        ctx_data = json.loads(row[0])
    except Exception as exc:
        log.error("redispatch: context_json inválido para mission=%s: %s", mission_id, exc)
        return

    ctx = MissionContext(
        mission_id        = mission_id,
        finalizer_id      = ctx_data["finalizer_id"],
        guardian_id       = ctx_data.get("guardian_id"),
        max_retries       = ctx_data.get("max_retries", 3),
        retry_delay_secs  = ctx_data.get("retry_delay_secs", 2.0),
        approval_ttl_secs = ctx_data.get("approval_ttl_secs", 86400),
        steps             = [StepSpec(**step) for step in ctx_data["steps"]],
    )
    hdrs = {"Authorization": f"Bearer {API_TOKEN}"}
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            registry = AgentRegistry(Session, client, _SELF_BASE_URL, hdrs)
            executor = MissionExecutor(ctx, registry, Session, client, _SELF_BASE_URL, hdrs)
            await executor.run()
    except Exception as exc:
        log.error("redispatch: executor falhou para mission=%s: %s", mission_id, exc)


@app.post("/missions/run", tags=["missions"])
async def run_mission(
    req: RunMissionRequest,
    authorization: Optional[str] = Header(default=None),
):
    verify_token(authorization)

    ctx = MissionContext(
        mission_id        = req.mission_id,
        finalizer_id      = req.finalizer_id,
        guardian_id       = req.guardian_id,
        max_retries       = req.max_retries,
        retry_delay_secs  = req.retry_delay_secs,
        approval_ttl_secs = req.approval_ttl_secs,
        steps             = [
            StepSpec(
                action      = s.action,
                target_path = s.target_path,
                payload     = s.payload,
                mode        = s.mode,
            )
            for s in req.steps
        ],
    )

    # Persistir contexto para redespacho autônomo pelo watchdog
    _ctx_json = json.dumps({
        "finalizer_id":     req.finalizer_id,
        "guardian_id":      req.guardian_id,
        "steps":            [
            {"action": s.action, "target_path": s.target_path,
             "payload": s.payload, "mode": s.mode}
            for s in req.steps
        ],
        "max_retries":       req.max_retries,
        "retry_delay_secs":  req.retry_delay_secs,
        "approval_ttl_secs": req.approval_ttl_secs,
    })
    with Session() as _s:
        _MissionControl.create(_s, req.mission_id)
        _s.execute(
            text("""
                UPDATE mission_control SET context_json=:ctx
                WHERE mission_id=:mid AND context_json IS NULL
            """),
            {"ctx": _ctx_json, "mid": req.mission_id},
        )
        _s.commit()

    hdrs = {"Authorization": authorization, "X-Correlation-Id": req.mission_id}
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            registry = AgentRegistry(Session, client, _SELF_BASE_URL, hdrs)
            executor = MissionExecutor(ctx, registry, Session, client, _SELF_BASE_URL, hdrs)
            await executor.run()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    summary = get_mission_summary(Session, req.mission_id)
    return {"mission_id": req.mission_id, "summary": summary}


# ---------------------------------------------------------------------------
# Robô-mãe — Approval endpoints
# ---------------------------------------------------------------------------

@app.get("/missions/{mission_id}/approval", tags=["missions"])
async def get_mission_approval(
    mission_id: str,
    authorization: Optional[str] = Header(default=None),
):
    verify_token(authorization)
    with Session() as s:
        row = s.execute(
            text("""
                SELECT id, step_index, status, decided_by, notes,
                       decided_at, expires_at, created_at, context_snapshot
                FROM approval_requests
                WHERE mission_id=:mid ORDER BY id DESC LIMIT 1
            """),
            {"mid": mission_id},
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Nenhum approval request encontrado")
    return {
        "mission_id":       mission_id,
        "approval_id":      row[0],
        "step_index":       row[1],
        "status":           row[2],
        "decided_by":       row[3],
        "notes":            row[4],
        "decided_at":       row[5],
        "expires_at":       row[6],
        "created_at":       row[7],
        "context_snapshot": json.loads(row[8]) if row[8] else None,
    }


@app.post("/missions/{mission_id}/approve", tags=["missions"])
async def approve_mission(
    mission_id: str,
    body: ApprovalDecisionRequest,
    authorization: Optional[str] = Header(default=None),
):
    verify_token(authorization)
    with Session() as s:
        ar = s.execute(
            text("""
                SELECT step_index, status, expires_at FROM approval_requests
                WHERE mission_id=:mid ORDER BY id DESC LIMIT 1
            """),
            {"mid": mission_id},
        ).fetchone()
    if ar is None:
        raise HTTPException(status_code=404, detail="Nenhum approval request encontrado")
    step_index, ar_status, expires_at = ar
    if ar_status == "approved":
        return {"ok": True, "status": "approved", "idempotent": True}
    if ar_status == "denied":
        raise HTTPException(status_code=409, detail="Approval já negado — não pode aprovar")
    if ar_status == "expired" or (ar_status == "PENDING" and _now_iso_main() > expires_at):
        raise HTTPException(status_code=410, detail="Approval expirado")
    with Session() as s:
        ok = _MissionControl.resume_approval(
            s, mission_id, step_index, "approved", body.decided_by, body.notes
        )
    if not ok:
        raise HTTPException(status_code=409, detail="Não foi possível aprovar (request expirado ou já decidido)")
    return {"ok": True, "status": "approved", "mission_id": mission_id}


@app.post("/missions/{mission_id}/deny", tags=["missions"])
async def deny_mission(
    mission_id: str,
    body: ApprovalDecisionRequest,
    authorization: Optional[str] = Header(default=None),
):
    verify_token(authorization)
    with Session() as s:
        ar = s.execute(
            text("""
                SELECT step_index, status, expires_at FROM approval_requests
                WHERE mission_id=:mid ORDER BY id DESC LIMIT 1
            """),
            {"mid": mission_id},
        ).fetchone()
    if ar is None:
        raise HTTPException(status_code=404, detail="Nenhum approval request encontrado")
    step_index, ar_status, expires_at = ar
    if ar_status == "denied":
        return {"ok": True, "status": "denied", "idempotent": True}
    if ar_status == "approved":
        raise HTTPException(status_code=409, detail="Approval já aprovado — não pode negar")
    if ar_status == "expired" or (ar_status == "PENDING" and _now_iso_main() > expires_at):
        raise HTTPException(status_code=410, detail="Approval expirado")
    with Session() as s:
        ok = _MissionControl.resume_approval(
            s, mission_id, step_index, "denied", body.decided_by, body.notes
        )
    if not ok:
        raise HTTPException(status_code=409, detail="Não foi possível negar (request expirado ou já decidido)")
    return {"ok": True, "status": "denied", "mission_id": mission_id}


def _now_iso_main() -> str:
    """UTC naive ISO — helper local para comparação nos endpoints de approval."""
    return datetime.utcnow().isoformat()


# ---------------------------------------------------------------------------
# MACROBLOCO D — Watchdog
# ---------------------------------------------------------------------------

@app.post("/watchdog/scan", tags=["watchdog"])
async def watchdog_scan(
    authorization: Optional[str] = Header(default=None),
):
    verify_token(authorization)
    result = await _watchdog_scanner.scan_once()
    return {
        "scanned":     result.scanned,
        "resumed":     result.resumed,
        "quarantined": result.quarantined,
        "failed":      result.failed,
        "noop":        result.noop,
    }


# ---------------------------------------------------------------------------
# Memory Service endpoints
# ---------------------------------------------------------------------------

@app.post("/memory/events", tags=["memory"], status_code=201)
async def memory_create_event(
    body: MemEventCreate,
    authorization: Optional[str] = Header(default=None),
):
    verify_token(authorization)
    eid = insert_episodic_event(
        Session, body.agent_id, body.event_type, body.summary,
        payload=body.payload, occurred_at=body.occurred_at,
    )
    return {"advisory_only": True, "id": eid}


@app.get("/memory/events", tags=["memory"])
async def memory_list_events(
    agent_id:   Optional[str] = None,
    event_type: Optional[str] = None,
    limit:      int           = 20,
    authorization: Optional[str] = Header(default=None),
):
    verify_token(authorization)
    return RetrievalGateway(Session).query_episodic(
        agent_id=agent_id, event_type=event_type, limit=limit
    )


@app.post("/memory/facts", tags=["memory"])
async def memory_upsert_fact(
    body: MemFactCreate,
    authorization: Optional[str] = Header(default=None),
):
    verify_token(authorization)
    fid = upsert_semantic_fact(
        Session, body.category, body.key, body.value,
        confidence=body.confidence, source=body.source,
    )
    return {"advisory_only": True, "id": fid}


@app.get("/memory/facts", tags=["memory"])
async def memory_list_facts(
    category: Optional[str] = None,
    key:      Optional[str] = None,
    authorization: Optional[str] = Header(default=None),
):
    verify_token(authorization)
    return RetrievalGateway(Session).query_semantic(category=category, key=key)


@app.post("/memory/patterns", tags=["memory"])
async def memory_upsert_pattern(
    body: MemPatternCreate,
    authorization: Optional[str] = Header(default=None),
):
    verify_token(authorization)
    pid = upsert_procedural_pattern(
        Session, body.name, body.description, body.steps,
        trigger_conditions=body.trigger_conditions,
        success_rate=body.success_rate,
    )
    return {"advisory_only": True, "id": pid}


@app.get("/memory/patterns", tags=["memory"])
async def memory_list_patterns(
    name: Optional[str] = None,
    authorization: Optional[str] = Header(default=None),
):
    verify_token(authorization)
    return RetrievalGateway(Session).query_procedural(name=name)


@app.post("/memory/graph/nodes", tags=["memory"], status_code=201)
async def memory_create_node(
    body: MemNodeCreate,
    authorization: Optional[str] = Header(default=None),
):
    verify_token(authorization)
    nid = insert_graph_node(Session, body.node_type, body.label,
                             properties=body.properties)
    return {"advisory_only": True, "id": nid}


@app.post("/memory/graph/edges", tags=["memory"], status_code=201)
async def memory_create_edge(
    body: MemEdgeCreate,
    authorization: Optional[str] = Header(default=None),
):
    verify_token(authorization)
    eid = insert_graph_edge(
        Session, body.source_id, body.relation, body.target_id,
        weight=body.weight, properties=body.properties,
    )
    return {"advisory_only": True, "id": eid}


@app.get("/memory/graph/neighbors/{node_id}", tags=["memory"])
async def memory_graph_neighbors(
    node_id:  str,
    relation: Optional[str] = None,
    authorization: Optional[str] = Header(default=None),
):
    verify_token(authorization)
    return RetrievalGateway(Session).query_graph(node_id=node_id, relation=relation)


@app.post("/memory/context", tags=["memory"])
async def memory_build_context(
    body: MemContextRequest,
    authorization: Optional[str] = Header(default=None),
):
    verify_token(authorization)
    return RetrievalGateway(Session).build_agent_context(body.agent_id)


@app.post("/memory/reflect", tags=["memory"])
async def memory_reflect(
    body: MemReflectRequest,
    authorization: Optional[str] = Header(default=None),
):
    verify_token(authorization)
    return RetrievalGateway(Session).reflect_and_consolidate(body.agent_id, body.intent)


@app.post("/memory/reflect/run", tags=["memory"])
async def memory_run_reflection(
    body: MemReflectRun,
    authorization: Optional[str] = Header(default=None),
):
    """
    Dispara uma rodada de reflexão fora do caminho crítico.
    Consolida sinais episódicos e ajusta success_rate de patterns (não toca usage_count).
    agent_id=None → reflexão global; agent_id fornecido → escopada ao agente.
    Retorna relatório advisory_only.
    """
    verify_token(authorization)
    return run_reflection(Session, agent_id=body.agent_id)


@app.get("/agents/{agent_id}/build-context", tags=["memory"])
async def agent_build_context(
    agent_id: str,
    authorization: Optional[str] = Header(default=None),
):
    """
    Constrói contexto enriquecido do agente:
    dados do agente (nome, role) + memória completa (4 tipos) + reflection_summary.
    Retorno é advisory_only — não governa decisões operacionais.
    """
    verify_token(authorization)
    with Session() as s:
        row = s.execute(
            text("SELECT id, name, role FROM agents WHERE id = :aid"),
            {"aid": agent_id},
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Agent not found")
    mem_ctx = RetrievalGateway(Session).build_agent_context(agent_id)
    return {
        "advisory_only": True,
        "agent_id":   row[0],
        "agent_name": row[1],
        "agent_role": row[2],
        "memory":     mem_ctx["data"],
    }


if os.environ.get("JOD_ENV") == "test":

    @app.post("/test/io-fail/set")
    async def test_set_io_fail(
        target_path: str,
        authorization: Optional[str] = Header(default=None),
    ):
        verify_token(authorization)
        app.state.io_fail_target = target_path
        return {"ok": True, "target_path": target_path}

    @app.post("/test/io-fail/clear")
    async def test_clear_io_fail(
        authorization: Optional[str] = Header(default=None),
    ):
        verify_token(authorization)
        app.state.io_fail_target = ""
        return {"ok": True}


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run("main_fase2:app", host="127.0.0.1", port=37777, reload=False)
