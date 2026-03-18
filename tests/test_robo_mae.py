import asyncio
import json
import sqlite3
import uuid

import httpx
import pytest
from pathlib import Path

BASE_URL = "http://127.0.0.1:37777"
HEADERS  = {"Authorization": "Bearer dev-token"}
_ROOT    = Path(__file__).parent.parent
DB_PATH  = str(_ROOT / "jod_robo.db")
BASE_DIR = _ROOT

_MANIFEST = {
    "allowed_actions": ["write_file", "read_file", "list_dir"],
    "allowed_paths":   ["agents/", "scripts/", "templates/", "tests/", "restricted/", "pending/"],
    "forbidden_paths": [
        "app/",
        "jod_brain/",
        ".env",
        "main_fase2.py",
        "jod_brain_main.py",
        "requirements.txt",
        "Dockerfile",
        "templates/finalizer_manifest.json",
    ],
    "allowed_hosts":      [],
    "requires_approval":  ["run_script", "git_push", "delete_file", "access_secret", "edit_core"],
}

_TARGET_APPLY       = "tests/rm_apply.txt"
_TARGET_VETO        = "restricted/rm_veto.txt"   # restricted/ → guardian bloqueia
_TARGET_IO_FAIL     = "tests/rm_io_fail.txt"
_TARGET_DRAFT       = "tests/rm_draft_activate.txt"
_TARGET_CONCURRENT  = "tests/rm_concurrent.txt"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _db(query: str, params: tuple = ()) -> list[dict]:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(query, params).fetchall()
    con.close()
    return [dict(r) for r in rows]


def _get_mission_log(mission_id: str) -> list[dict]:
    return _db(
        "SELECT * FROM mission_log WHERE mission_id = ? ORDER BY id",
        (mission_id,),
    )


def _get_integration_by_transaction(transaction_id: str) -> dict | None:
    rows = _db(
        "SELECT * FROM integration_audit WHERE transaction_id = ? LIMIT 1",
        (transaction_id,),
    )
    return rows[0] if rows else None


def _assert_no_shadow_for(target_path: str) -> None:
    basename = Path(target_path).name
    shadows  = list(BASE_DIR.rglob(f".{basename}.*.jod_tmp"))
    assert shadows == [], f"shadow órfão para {target_path}: {shadows}"


def _set_io_fail(target_path: str) -> None:
    r = httpx.post(
        f"{BASE_URL}/test/io-fail/set",
        headers=HEADERS,
        params={"target_path": target_path},
    )
    assert r.status_code == 200, (
        f"set io-fail falhou ({r.status_code}): {r.text}\n"
        f"Servidor rodando com JOD_ENV=test?"
    )


def _clear_io_fail() -> None:
    r = httpx.post(f"{BASE_URL}/test/io-fail/clear", headers=HEADERS)
    assert r.status_code == 200, f"clear io-fail falhou: {r.text}"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def guardian_id():
    r = httpx.post(
        f"{BASE_URL}/agents/guardian",
        headers=HEADERS,
        json={"name": "guardian-rm-test"},
    )
    assert r.status_code == 200, f"criar guardian falhou: {r.text}"
    gid = r.json()["agent_id"]

    r = httpx.post(f"{BASE_URL}/agents/{gid}/guardian/validate", headers=HEADERS)
    assert r.status_code == 200, f"validar guardian falhou: {r.text}"

    r = httpx.post(f"{BASE_URL}/agents/{gid}/guardian/activate", headers=HEADERS)
    assert r.status_code == 200, f"ativar guardian falhou: {r.text}"

    yield gid


@pytest.fixture(scope="module")
def finalizer_id():
    r = httpx.post(
        f"{BASE_URL}/agents/finalizer",
        headers=HEADERS,
        json={"name": "finalizer-rm-test", "manifest": _MANIFEST},
    )
    assert r.status_code == 200, f"criar finalizer falhou: {r.text}"
    fid = r.json()["agent_id"]

    r = httpx.post(f"{BASE_URL}/agents/{fid}/finalizer/validate", headers=HEADERS)
    assert r.status_code == 200, f"validar finalizer falhou: {r.text}"

    r = httpx.post(f"{BASE_URL}/agents/{fid}/finalizer/activate", headers=HEADERS)
    assert r.status_code == 200, f"ativar finalizer falhou: {r.text}"

    yield fid


@pytest.fixture(scope="module")
def finalizer_draft_id():
    """Finalizer criado mas NÃO validado nem ativado — permanece em draft."""
    r = httpx.post(
        f"{BASE_URL}/agents/finalizer",
        headers=HEADERS,
        json={"name": "finalizer-rm-draft", "manifest": _MANIFEST},
    )
    assert r.status_code == 200, f"criar finalizer-draft falhou: {r.text}"
    yield r.json()["agent_id"]


@pytest.fixture(autouse=True)
def limpar_io_fail_hook():
    _clear_io_fail()
    yield
    _clear_io_fail()


# ---------------------------------------------------------------------------
# T1 — missão apply aprovada
# ---------------------------------------------------------------------------

def test_t1_mission_apply_aprovada(finalizer_id, guardian_id):
    mission_id = f"t1-{uuid.uuid4()}"

    r = httpx.post(
        f"{BASE_URL}/missions/run",
        headers=HEADERS,
        json={
            "mission_id":   mission_id,
            "finalizer_id": finalizer_id,
            "guardian_id":  guardian_id,
            "steps": [{
                "action":      "write_file",
                "target_path": _TARGET_APPLY,
                "payload":     "conteudo t1",
                "mode":        "apply",
            }],
        },
    )
    assert r.status_code == 200, r.text

    body    = r.json()
    summary = body["summary"]
    assert summary["success"]        is True,  f"summary.success falso: {summary}"
    assert summary["steps_applied"]  == 1
    assert summary["steps_vetoed"]   == 0
    assert summary["steps_failed"]   == 0
    assert summary["steps_total"]    == 1

    # mission_log gravado corretamente
    logs = _get_mission_log(mission_id)
    assert len(logs) == 1
    assert logs[0]["status"]       == "applied"
    assert logs[0]["io_committed"] == 1

    # transaction_id presente e consistente com integration_audit
    tid = logs[0]["transaction_id"]
    assert tid, "transaction_id ausente em mission_log"
    int_rec = _get_integration_by_transaction(tid)
    assert int_rec is not None,        "registro ausente em integration_audit"
    assert int_rec["io_committed"] == 1, "io_committed=0 em integration_audit"

    # arquivo escrito e sem shadow órfão
    assert (BASE_DIR / _TARGET_APPLY).exists(), "arquivo não foi criado"
    _assert_no_shadow_for(_TARGET_APPLY)


# ---------------------------------------------------------------------------
# T2 — missão com veto (blocked)
# ---------------------------------------------------------------------------

def test_t2_mission_veto_blocked(finalizer_id, guardian_id):
    mission_id = f"t2-{uuid.uuid4()}"

    r = httpx.post(
        f"{BASE_URL}/missions/run",
        headers=HEADERS,
        json={
            "mission_id":   mission_id,
            "finalizer_id": finalizer_id,
            "guardian_id":  guardian_id,
            "steps": [{
                "action":      "write_file",
                "target_path": _TARGET_VETO,
                "payload":     "nunca escrito",
                "mode":        "apply",
            }],
        },
    )
    assert r.status_code == 200, r.text

    summary = r.json()["summary"]
    assert summary["success"]       is False
    assert summary["steps_vetoed"]  == 1
    assert summary["steps_applied"] == 0
    assert summary["steps_failed"]  == 0

    # mission_log: status=vetoed, io_committed=0
    logs = _get_mission_log(mission_id)
    assert len(logs) == 1
    assert logs[0]["status"]       == "vetoed"
    assert logs[0]["io_committed"] == 0

    # arquivo não criado, sem shadow
    assert not (BASE_DIR / _TARGET_VETO).exists()
    _assert_no_shadow_for(_TARGET_VETO)


# ---------------------------------------------------------------------------
# T3 — ensure_active com agente em draft
# ---------------------------------------------------------------------------

def test_t3_ensure_active_from_draft(finalizer_draft_id, guardian_id):
    mission_id = f"t3-{uuid.uuid4()}"

    # Confirmar estado inicial no DB
    rows = _db("SELECT status FROM agents WHERE id = ?", (finalizer_draft_id,))
    assert rows, "agente não encontrado no DB"
    assert rows[0]["status"] == "draft", f"status esperado 'draft', obtido '{rows[0]['status']}'"

    r = httpx.post(
        f"{BASE_URL}/missions/run",
        headers=HEADERS,
        json={
            "mission_id":   mission_id,
            "finalizer_id": finalizer_draft_id,
            "guardian_id":  guardian_id,
            "steps": [{
                "action":      "write_file",
                "target_path": _TARGET_DRAFT,
                "payload":     "draft ativado implicitamente",
                "mode":        "apply",
            }],
        },
    )
    assert r.status_code == 200, f"esperado 200, obtido {r.status_code}: {r.text}"

    summary = r.json()["summary"]
    assert summary["success"]       is True
    assert summary["steps_applied"] == 1

    # Agente deve estar active após a missão
    rows = _db("SELECT status FROM agents WHERE id = ?", (finalizer_draft_id,))
    assert rows[0]["status"] == "active", (
        f"agente ainda não está active: {rows[0]['status']}"
    )


# ---------------------------------------------------------------------------
# T4 — io_committed: falha de I/O detectada pela missão
# ---------------------------------------------------------------------------

def test_t4_io_fail_detectado(finalizer_id, guardian_id):
    """
    O hook de teste força falha de I/O no servidor (retorna 500).
    O executor deve marcar o step como 'error' e summary.success=False.
    Confirma que mission_log registra o fracasso e io_committed=0/None.
    """
    mission_id = f"t4-{uuid.uuid4()}"
    _set_io_fail(_TARGET_IO_FAIL)

    r = httpx.post(
        f"{BASE_URL}/missions/run",
        headers=HEADERS,
        json={
            "mission_id":   mission_id,
            "finalizer_id": finalizer_id,
            "guardian_id":  guardian_id,
            "steps": [{
                "action":      "write_file",
                "target_path": _TARGET_IO_FAIL,
                "payload":     "vai falhar",
                "mode":        "apply",
            }],
        },
    )
    assert r.status_code == 200, r.text  # missão em si retorna 200

    summary = r.json()["summary"]
    assert summary["success"]      is False
    assert summary["steps_failed"] == 1
    assert summary["steps_applied"] == 0

    # mission_log: status=error
    logs = _get_mission_log(mission_id)
    assert len(logs) == 1
    assert logs[0]["status"] == "error"

    # arquivo não criado, sem shadow
    assert not (BASE_DIR / _TARGET_IO_FAIL).exists()
    _assert_no_shadow_for(_TARGET_IO_FAIL)


# ---------------------------------------------------------------------------
# T5 — regressão: missão dry_run não escreve arquivo
# ---------------------------------------------------------------------------

def test_t5_dry_run_nao_escreve(finalizer_id, guardian_id):
    mission_id = f"t5-{uuid.uuid4()}"
    target     = "tests/rm_dry_run.txt"

    r = httpx.post(
        f"{BASE_URL}/missions/run",
        headers=HEADERS,
        json={
            "mission_id":   mission_id,
            "finalizer_id": finalizer_id,
            "guardian_id":  guardian_id,
            "steps": [{
                "action":      "write_file",
                "target_path": target,
                "payload":     "dry run payload",
                "mode":        "dry_run",
            }],
        },
    )
    assert r.status_code == 200, r.text

    summary = r.json()["summary"]
    # dry_run_ok não é "applied" nem "vetoed" nem "error" — success=False
    # (steps_total=1 mas steps_applied=0 e steps_failed=0 e steps_vetoed=0)
    assert summary["steps_applied"] == 0
    assert summary["steps_failed"]  == 0
    assert summary["steps_vetoed"]  == 0

    logs = _get_mission_log(mission_id)
    assert len(logs) == 1
    assert logs[0]["status"] == "dry_run_ok"

    assert not (BASE_DIR / target).exists()


# ---------------------------------------------------------------------------
# T6 — X-Correlation-Id echoed back na resposta de /missions/run
# ---------------------------------------------------------------------------

def test_t6_correlation_id_echoed_in_response(finalizer_id, guardian_id):
    """
    O caller envia X-Correlation-Id = mission_id na requisição outer.
    O _CorrelationMiddleware deve ecoar o mesmo valor no header da resposta.
    """
    mission_id = f"t6-{uuid.uuid4()}"

    r = httpx.post(
        f"{BASE_URL}/missions/run",
        headers={**HEADERS, "X-Correlation-Id": mission_id},
        json={
            "mission_id":   mission_id,
            "finalizer_id": finalizer_id,
            "guardian_id":  guardian_id,
            "steps": [{
                "action":      "write_file",
                "target_path": "tests/rm_xcid.txt",
                "payload":     "xcid test",
                "mode":        "apply",
            }],
        },
    )
    assert r.status_code == 200, r.text

    # Middleware deve ecoar X-Correlation-Id de volta
    assert r.headers.get("x-correlation-id") == mission_id, (
        f"X-Correlation-Id esperado={mission_id}, "
        f"obtido={r.headers.get('x-correlation-id')}"
    )

    # mission_log.correlation_id = mission_id
    logs = _get_mission_log(mission_id)
    assert len(logs) == 1
    assert logs[0]["correlation_id"] == mission_id, (
        f"mission_log.correlation_id={logs[0]['correlation_id']} != {mission_id}"
    )


# ---------------------------------------------------------------------------
# T7 — logs do servidor carregam mission_id como correlation_id
# ---------------------------------------------------------------------------

def test_t7_log_entries_carry_mission_id(guardian_id):
    """
    Usa um finalizer em draft criado inline, para forçar calls reais de
    validate+activate dentro do ensure_active. Essas chamadas passam
    X-Correlation-Id = mission_id, e o servidor gera log.info("Agente ativado: ...")
    com correlation_id = mission_id. O uvicorn.log deve refletir isso.
    """
    # Criar um finalizer novo em estado draft
    r = httpx.post(
        f"{BASE_URL}/agents/finalizer",
        headers=HEADERS,
        json={"name": "finalizer-t7-xcid", "manifest": _MANIFEST},
    )
    assert r.status_code == 200, f"criar finalizer t7 falhou: {r.text}"
    fid_t7 = r.json()["agent_id"]

    mission_id = f"t7-{uuid.uuid4()}"
    log_path   = BASE_DIR / "uvicorn.log"

    # ensure_active vai chamar validate + activate, gerando log.info com mission_id
    r = httpx.post(
        f"{BASE_URL}/missions/run",
        headers=HEADERS,
        json={
            "mission_id":   mission_id,
            "finalizer_id": fid_t7,
            "guardian_id":  guardian_id,
            "steps": [{
                "action":      "write_file",
                "target_path": "tests/rm_xcid2.txt",
                "payload":     "xcid log proof",
                "mode":        "apply",
            }],
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["summary"]["success"] is True

    # Verificar no uvicorn.log que os requests internos carregam mission_id
    assert log_path.exists(), "uvicorn.log não encontrado"
    matched = []
    for line in log_path.read_text(errors="replace").splitlines():
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if entry.get("correlation_id") == mission_id:
            matched.append(entry)

    assert len(matched) > 0, (
        f"Nenhuma entrada em uvicorn.log com correlation_id={mission_id}\n"
        f"O executor não está propagando X-Correlation-Id nos requests internos."
    )


# ---------------------------------------------------------------------------
# T8 — B2: serialização por target_path — 5 missões concorrentes, mesmo path
# ---------------------------------------------------------------------------

def test_t8_concurrent_missions_same_path_serialized(finalizer_id, guardian_id):
    """
    5 missões disparadas simultaneamente escrevem no mesmo target_path.
    O executor serializa via _get_exec_path_lock: apenas uma missão por vez
    detém o lock e faz o request de execução.
    Resultado esperado:
      - todas as 5 retornam 200 com success=True
      - conteúdo final é um dos 5 payloads (sem corrupção)
      - nenhum shadow file órfão
      - mission_log registra 5 steps com status=applied
    """
    payloads = [f"conteudo_{i}" for i in range(5)]

    async def _write(i):
        async with httpx.AsyncClient(base_url=BASE_URL, headers=HEADERS, timeout=30.0) as c:
            return await c.post(
                "/missions/run",
                json={
                    "mission_id":   f"t8-{i}-{uuid.uuid4()}",
                    "finalizer_id": finalizer_id,
                    "guardian_id":  guardian_id,
                    "steps": [{
                        "action":      "write_file",
                        "target_path": _TARGET_CONCURRENT,
                        "payload":     payloads[i],
                        "mode":        "apply",
                    }],
                },
            )

    async def _run():
        return await asyncio.gather(*[_write(i) for i in range(5)])

    responses = asyncio.run(_run())

    assert all(r.status_code == 200 for r in responses), \
        f"requests com falha: {[r.text for r in responses if r.status_code != 200]}"

    # Conteúdo final deve ser um dos 5 payloads (sem corrupção)
    content = (BASE_DIR / _TARGET_CONCURRENT).read_text(encoding="utf-8")
    assert content in payloads, f"corrupção detectada: {repr(content)}"

    # Busca precisa de shadows por basename
    basename = Path(_TARGET_CONCURRENT).name
    shadows  = list(BASE_DIR.rglob(f".{basename}.*.jod_tmp"))
    assert shadows == [], f"shadow órfão encontrado: {shadows}"

    # Todas as 5 missões registradas em mission_log com status=applied
    for resp in responses:
        body = resp.json()
        mid  = body["mission_id"]
        logs = _get_mission_log(mid)
        assert len(logs) == 1,                   f"mission_log ausente para {mid}"
        assert logs[0]["status"] == "applied",   f"status inesperado: {logs[0]['status']}"
        assert logs[0]["io_committed"] == 1,     f"io_committed=0 para {mid}"
