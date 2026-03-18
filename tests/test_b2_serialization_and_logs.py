import httpx
import asyncio
import pytest
import uuid
from pathlib import Path

BASE_URL = "http://127.0.0.1:37777"
HEADERS  = {"Authorization": "Bearer dev-token"}
BASE_DIR = Path(__file__).parent.parent

_MANIFEST = {
    "allowed_actions": ["write_file", "read_file", "list_dir"],
    "allowed_paths": ["agents/", "scripts/", "templates/", "tests/"],
    "forbidden_paths": [
        "app/", "jod_brain/", ".env", "main_fase2.py",
        "jod_brain_main.py", "requirements.txt", "Dockerfile",
        "templates/finalizer_manifest.json",
    ],
    "allowed_hosts": [],
    "requires_approval": [
        "run_script", "git_push", "delete_file",
        "access_secret", "edit_core",
    ],
}


@pytest.fixture(scope="module")
def finalizer_id():
    r = httpx.post(
        f"{BASE_URL}/agents/finalizer",
        headers=HEADERS,
        json={"name": f"finalizer-b2-{uuid.uuid4().hex[:6]}", "manifest": _MANIFEST},
    )
    assert r.status_code == 200, f"criar falhou: {r.text}"
    fid = r.json()["agent_id"]
    httpx.post(f"{BASE_URL}/agents/{fid}/finalizer/validate", headers=HEADERS)
    httpx.post(f"{BASE_URL}/agents/{fid}/finalizer/activate", headers=HEADERS)
    yield fid


def test_concurrent_writes_same_path_serialized(finalizer_id):
    target = "tests/b2_concurrent.txt"
    results = []

    async def _write(payload):
        async with httpx.AsyncClient(base_url=BASE_URL, headers=HEADERS) as c:
            return await c.post(
                f"/agents/{finalizer_id}/finalizer/execute",
                json={"mode": "apply", "action": "write_file",
                      "target_path": target, "payload": payload},
            )

    async def _run():
        r1, r2 = await asyncio.gather(_write("conteudo_A"), _write("conteudo_B"))
        results.extend([r1, r2])

    asyncio.run(_run())
    assert all(r.status_code == 200 for r in results),         f"requests falharam: {[r.text for r in results]}"
    content = (BASE_DIR / target).read_text(encoding="utf-8")
    assert content in ("conteudo_A", "conteudo_B"),         f"corrupção detectada: {repr(content)}"


def test_sequential_writes_same_path(finalizer_id):
    target = "tests/b2_sequential.txt"
    for p in ("primeiro", "segundo", "terceiro"):
        r = httpx.post(
            f"{BASE_URL}/agents/{finalizer_id}/finalizer/execute",
            headers=HEADERS,
            json={"mode": "apply", "action": "write_file",
                  "target_path": target, "payload": p},
        )
        assert r.status_code == 200, r.text
    assert (BASE_DIR / target).read_text(encoding="utf-8") == "terceiro"


def test_concurrent_different_paths_no_block(finalizer_id):
    results = []

    async def _write(target, payload):
        async with httpx.AsyncClient(base_url=BASE_URL, headers=HEADERS) as c:
            return await c.post(
                f"/agents/{finalizer_id}/finalizer/execute",
                json={"mode": "apply", "action": "write_file",
                      "target_path": target, "payload": payload},
            )

    async def _run():
        r1, r2 = await asyncio.gather(
            _write("tests/b2_path_a.txt", "A"),
            _write("tests/b2_path_b.txt", "B"),
        )
        results.extend([r1, r2])

    asyncio.run(_run())
    assert all(r.status_code == 200 for r in results)
    assert (BASE_DIR / "tests/b2_path_a.txt").read_text(encoding="utf-8") == "A"
    assert (BASE_DIR / "tests/b2_path_b.txt").read_text(encoding="utf-8") == "B"


def test_response_has_correlation_id_header(finalizer_id):
    r = httpx.post(
        f"{BASE_URL}/agents/{finalizer_id}/finalizer/execute",
        headers=HEADERS,
        json={"mode": "apply", "action": "write_file",
              "target_path": "tests/b2_cid.txt", "payload": "cid test"},
    )
    assert r.status_code == 200, r.text
    assert "x-correlation-id" in r.headers,         "header X-Correlation-Id ausente na resposta"
    assert len(r.headers["x-correlation-id"]) == 36,         f"formato inválido: {r.headers['x-correlation-id']}"


def test_client_correlation_id_echoed(finalizer_id):
    cid = str(uuid.uuid4())
    r = httpx.post(
        f"{BASE_URL}/agents/{finalizer_id}/finalizer/execute",
        headers={**HEADERS, "X-Correlation-Id": cid},
        json={"mode": "apply", "action": "write_file",
              "target_path": "tests/b2_cid_echo.txt", "payload": "echo"},
    )
    assert r.status_code == 200, r.text
    assert r.headers.get("x-correlation-id") == cid,         f"esperado {cid}, obtido {r.headers.get('x-correlation-id')}"


def test_no_regression(finalizer_id):
    r = httpx.post(
        f"{BASE_URL}/agents/{finalizer_id}/finalizer/execute",
        headers=HEADERS,
        json={"mode": "apply", "action": "write_file",
              "target_path": "tests/b2_regression.txt", "payload": "ok"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["applied"] is True


def test_json_formatter_ts_has_real_microseconds():
    """P2 — contrato: ts deve ser ISO8601 com 6 dígitos de microsegundo reais (não literal %f)."""
    import json as _json
    import logging
    import os
    import re
    import sys
    import tempfile
    import importlib.util

    _root = str(BASE_DIR)
    if _root not in sys.path:
        sys.path.insert(0, _root)

    _tmpdb = tempfile.mkdtemp()
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmpdb}/ts_test.db")

    spec = importlib.util.spec_from_file_location(
        "_main_fase2_ts", str(BASE_DIR / "main_fase2.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    formatter = mod._JsonFormatter()
    record = logging.LogRecord(
        name="ts-test", level=logging.INFO,
        pathname="", lineno=0, msg="verifica ts", args=(), exc_info=None,
    )
    out = formatter.format(record)
    data = _json.loads(out)
    ts = data["ts"]

    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}", ts), (
        f"ts deve ser ISO8601 com 6 dígitos de microsegundo, obtido: {ts!r}"
    )
    assert "%f" not in ts, f"ts contém literal %f: {ts!r}"
