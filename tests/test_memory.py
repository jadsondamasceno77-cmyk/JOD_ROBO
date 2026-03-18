"""Testes unitários para jod_brain.memory."""
import sys, os, json, uuid, pytest, tempfile
sys.path.insert(0, "/home/wsl/JOD_ROBO")
from jod_brain import memory as mem

def test_load_retorna_estrutura_vazia_se_nao_existe():
    result = mem.load("/tmp/nao_existe_xyz.json")
    assert "execucoes" in result
    assert "aprendizados" in result
    assert "agentes_criados" in result
    assert result["execucoes"] == []

def test_save_e_load_roundtrip(tmp_path):
    path = str(tmp_path / "memoria.json")
    data = {"execucoes": [{"ts": "2026-01-01", "task": "teste"}],
            "aprendizados": ["aprendizado 1"],
            "agentes_criados": []}
    mem.save(path, data)
    loaded = mem.load(path)
    assert loaded["execucoes"][0]["task"] == "teste"
    assert loaded["aprendizados"][0] == "aprendizado 1"

def test_record_adiciona_execucao(tmp_path):
    path = str(tmp_path / "memoria.json")
    memory = mem.load(path)
    updated = mem.record(memory, "id_001", "tarefa teste",
                         "resumo ok", ["agents/test.py"], "agente", "aprendi algo")
    assert len(updated["execucoes"]) == 1
    assert updated["execucoes"][0]["task"] == "tarefa teste"
    assert updated["aprendizados"][0] == "aprendi algo"

def test_record_limita_50_execucoes(tmp_path):
    path = str(tmp_path / "memoria.json")
    memory = mem.load(path)
    for i in range(60):
        memory = mem.record(memory, f"id_{i}", f"tarefa {i}",
                            "resumo", [], "script")
    assert len(memory["execucoes"]) == 50

def test_record_limita_20_aprendizados(tmp_path):
    path = str(tmp_path / "memoria.json")
    memory = mem.load(path)
    for i in range(25):
        memory = mem.record(memory, f"id_{i}", "tarefa",
                            "resumo", [], "script", f"aprendizado {i}")
    assert len(memory["aprendizados"]) == 20

def test_context_sem_historico():
    memory = {"execucoes": [], "aprendizados": []}
    result = mem.context(memory)
    assert "Nenhuma execucao" in result

def test_context_com_historico():
    memory = {
        "execucoes": [{"ts": "2026-01-01 10:00", "task": "criar agente",
                       "summary": "criado", "files": ["agents/x.py"]}],
        "aprendizados": ["usar pydantic"]
    }
    result = mem.context(memory)
    assert "criar agente" in result
    assert "usar pydantic" in result

if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# =============================================================================
# MACROBLOCO B — memory_service (T23–T36)
# =============================================================================

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from memory_service.policy_guard import (
    CRITICAL_OPERATIONS,
    MemoryGovernanceError,
    assert_advisory_only,
    enforce_advisory,
    wrap_advisory,
)
from memory_service.migrate import _migrate_memory_service
from memory_service.storage import (
    find_node_by_label,
    insert_episodic_event,
    insert_graph_edge,
    insert_graph_node,
    list_episodic_events,
    list_graph_neighbors,
    list_graph_nodes,
    list_procedural_patterns,
    list_semantic_facts,
    upsert_procedural_pattern,
    upsert_semantic_fact,
)
from memory_service.retrieval_gateway import RetrievalGateway


def _make_mem_sf():
    """Session factory SQLite in-memory com tabelas de memory_service."""
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    _migrate_memory_service(eng)
    Sess = sessionmaker(bind=eng, autoflush=False, autocommit=False)

    @contextmanager
    def sf():
        s = Sess()
        try:
            yield s
        finally:
            s.close()

    return sf


# T23 — policy_guard: CRITICAL_OPERATIONS levanta MemoryGovernanceError
def test_T23_policy_guard_critical_operations_raise():
    for op in CRITICAL_OPERATIONS:
        with pytest.raises(MemoryGovernanceError, match="proibida"):
            assert_advisory_only(op)


# T24 — policy_guard: operação normal não levanta; wrap_advisory correto
def test_T24_policy_guard_safe_and_wrap():
    assert_advisory_only("query_episodic")   # não levanta
    result = wrap_advisory({"x": 1})
    assert result["advisory_only"] is True
    assert result["data"] == {"x": 1}


# T25 — storage: insert + list episodic events com filtro por agent_id
def test_T25_episodic_insert_and_list():
    sf = _make_mem_sf()
    eid = insert_episodic_event(sf, "agente-A", "task_done", "resumo ok",
                                payload={"k": "v"})
    insert_episodic_event(sf, "agente-B", "task_done", "outro")
    results = list_episodic_events(sf, agent_id="agente-A")
    assert len(results) == 1
    assert results[0]["id"] == eid
    assert results[0]["payload"] == {"k": "v"}
    assert results[0]["event_type"] == "task_done"


# T26 — storage: upsert semantic fact (UNIQUE category+key)
def test_T26_semantic_upsert_idempotency():
    sf = _make_mem_sf()
    upsert_semantic_fact(sf, "sistema", "versao", "1.0")
    upsert_semantic_fact(sf, "sistema", "versao", "2.0", confidence=0.9)
    facts = list_semantic_facts(sf, category="sistema", key="versao")
    assert len(facts) == 1
    assert facts[0]["value"] == "2.0"
    assert facts[0]["confidence"] == 0.9


# T27 — storage: upsert procedural pattern (UNIQUE name)
def test_T27_procedural_upsert_idempotency():
    sf = _make_mem_sf()
    upsert_procedural_pattern(sf, "pat-x", "desc v1", ["step1"], success_rate=0.5)
    upsert_procedural_pattern(sf, "pat-x", "desc v2", ["step1", "step2"],
                              success_rate=0.8)
    patterns = list_procedural_patterns(sf, name="pat-x")
    assert len(patterns) == 1
    assert patterns[0]["description"] == "desc v2"
    assert patterns[0]["steps"] == ["step1", "step2"]


# T28 — storage: graph node + edge + UNIQUE(source, relation, target)
def test_T28_graph_node_edge_unique():
    sf = _make_mem_sf()
    n1 = insert_graph_node(sf, "agent", "Agente-A")
    n2 = insert_graph_node(sf, "agent", "Agente-B")
    insert_graph_edge(sf, n1, "delega_para", n2, weight=0.9)
    insert_graph_edge(sf, n1, "delega_para", n2)   # duplicata — INSERT OR IGNORE
    neighbors = list_graph_neighbors(sf, n1)
    assert len(neighbors) == 1
    assert neighbors[0]["relation"] == "delega_para"
    assert neighbors[0]["target_label"] == "Agente-B"


# T29 — retrieval_gateway: build_agent_context retorna episodic+semantic+procedural+graph
def test_T29_build_agent_context_com_graph():
    sf = _make_mem_sf()
    insert_episodic_event(sf, "ag-1", "step", "fez algo")
    upsert_semantic_fact(sf, "cat", "k", "v")
    upsert_procedural_pattern(sf, "pp", "d", ["s1"])
    gw = RetrievalGateway(sf)
    ctx = gw.build_agent_context("ag-1")
    assert ctx["advisory_only"] is True
    data = ctx["data"]
    assert len(data["episodic"]) == 1
    assert len(data["semantic"]) == 1
    assert len(data["procedural"]) == 1
    assert "graph" in data            # fechamento 1: graph sempre presente
    assert isinstance(data["graph"], list)


# T30 — retrieval_gateway: reflect_and_consolidate stub retorna pending_consolidation
def test_T30_reflect_and_consolidate_stub():
    sf = _make_mem_sf()
    gw = RetrievalGateway(sf)
    result = gw.reflect_and_consolidate("ag-2", "consolidar padrões de deploy")
    assert result["advisory_only"] is True
    assert result["data"]["status"] == "pending_consolidation"
    assert "event_id" in result["data"]
    events = list_episodic_events(sf, agent_id="ag-2",
                                  event_type="consolidation_intent")
    assert len(events) == 1
    assert events[0]["summary"] == "consolidar padrões de deploy"


# T31 — build_agent_context: graph prioriza neighbors quando agente tem nó no grafo
def test_T31_build_agent_context_graph_prioriza_neighbors():
    sf = _make_mem_sf()
    # Criar nó com label = agent_id e um vizinho
    n_agent = insert_graph_node(sf, "agent", "ag-graph")
    n_other = insert_graph_node(sf, "resource", "recurso-X")
    insert_graph_edge(sf, n_agent, "usa", n_other)
    # Criar outros nós sem relação com ag-graph
    insert_graph_node(sf, "concept", "conceito-Y")
    gw = RetrievalGateway(sf)
    ctx = gw.build_agent_context("ag-graph")
    data = ctx["data"]
    # Deve retornar neighbors (1 aresta), não a lista genérica (3 nós)
    assert len(data["graph"]) == 1
    assert data["graph"][0]["relation"] == "usa"
    assert data["graph"][0]["target_label"] == "recurso-X"


# T32 — build_agent_context: fallback para nós recentes quando sem vínculo específico
def test_T32_build_agent_context_graph_fallback_nos_recentes():
    sf = _make_mem_sf()
    insert_graph_node(sf, "concept", "no-A")
    insert_graph_node(sf, "concept", "no-B")
    gw = RetrievalGateway(sf)
    # "ag-sem-no" não tem nó no grafo → fallback para list_graph_nodes
    ctx = gw.build_agent_context("ag-sem-no")
    data = ctx["data"]
    assert isinstance(data["graph"], list)
    assert len(data["graph"]) == 2    # os 2 nós criados


# T33 — policy_guard: enforce_advisory levanta MemoryGovernanceError quando advisory_only=False
def test_T33_enforce_advisory_raises_quando_nao_advisory():
    with pytest.raises(MemoryGovernanceError, match="advisory_only"):
        enforce_advisory({"advisory_only": False, "data": {}})
    with pytest.raises(MemoryGovernanceError):
        enforce_advisory({"data": "sem a chave advisory_only"})


# ---------------------------------------------------------------------------
# T34–T38 — Integração de endpoint (requer servidor em http://127.0.0.1:37777)
# ---------------------------------------------------------------------------

import httpx as _httpx

_BASE_MEM  = "http://127.0.0.1:37777"
_HDRS_MEM  = {"Authorization": "Bearer dev-token"}


def test_T34_endpoint_events_create_and_list():
    r = _httpx.post(f"{_BASE_MEM}/memory/events", headers=_HDRS_MEM, json={
        "agent_id": "ag-ep-T34", "event_type": "test_run", "summary": "evento T34",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["advisory_only"] is True
    eid = body["id"]

    r2 = _httpx.get(f"{_BASE_MEM}/memory/events",
                    params={"agent_id": "ag-ep-T34"}, headers=_HDRS_MEM)
    assert r2.status_code == 200
    assert r2.json()["advisory_only"] is True
    assert any(e["id"] == eid for e in r2.json()["data"])


def test_T35_endpoint_facts_upsert_and_list():
    _httpx.post(f"{_BASE_MEM}/memory/facts", headers=_HDRS_MEM, json={
        "category": "cfg-T35", "key": "timeout", "value": "30",
    })
    _httpx.post(f"{_BASE_MEM}/memory/facts", headers=_HDRS_MEM, json={
        "category": "cfg-T35", "key": "timeout", "value": "60",
    })
    r = _httpx.get(f"{_BASE_MEM}/memory/facts",
                   params={"category": "cfg-T35", "key": "timeout"},
                   headers=_HDRS_MEM)
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) == 1
    assert data[0]["value"] == "60"


def test_T36_endpoint_patterns_upsert_and_list():
    _httpx.post(f"{_BASE_MEM}/memory/patterns", headers=_HDRS_MEM, json={
        "name": f"pat-T36", "description": "padrão de teste",
        "steps": ["a", "b"], "success_rate": 0.75,
    })
    r = _httpx.get(f"{_BASE_MEM}/memory/patterns",
                   params={"name": "pat-T36"}, headers=_HDRS_MEM)
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) == 1
    assert data[0]["steps"] == ["a", "b"]


def test_T37_endpoint_graph_nodes_edges_neighbors():
    r_n1 = _httpx.post(f"{_BASE_MEM}/memory/graph/nodes", headers=_HDRS_MEM,
                        json={"node_type": "agent", "label": f"Ag-T37-A-{uuid.uuid4().hex[:4]}"})
    assert r_n1.status_code == 201
    n1 = r_n1.json()["id"]

    r_n2 = _httpx.post(f"{_BASE_MEM}/memory/graph/nodes", headers=_HDRS_MEM,
                        json={"node_type": "agent", "label": f"Ag-T37-B-{uuid.uuid4().hex[:4]}"})
    n2 = r_n2.json()["id"]

    r_e = _httpx.post(f"{_BASE_MEM}/memory/graph/edges", headers=_HDRS_MEM, json={
        "source_id": n1, "relation": "colabora_com", "target_id": n2, "weight": 0.8,
    })
    assert r_e.status_code == 201

    # duplicata — INSERT OR IGNORE
    r_e2 = _httpx.post(f"{_BASE_MEM}/memory/graph/edges", headers=_HDRS_MEM, json={
        "source_id": n1, "relation": "colabora_com", "target_id": n2,
    })
    assert r_e2.status_code == 201

    r_nb = _httpx.get(f"{_BASE_MEM}/memory/graph/neighbors/{n1}", headers=_HDRS_MEM)
    assert r_nb.status_code == 200
    nb = r_nb.json()["data"]
    assert len(nb) == 1
    assert nb[0]["relation"] == "colabora_com"


def test_T38_endpoint_context_build():
    _httpx.post(f"{_BASE_MEM}/memory/events", headers=_HDRS_MEM, json={
        "agent_id": "ag-ctx-T38", "event_type": "done", "summary": "seed T38",
    })
    r = _httpx.post(f"{_BASE_MEM}/memory/context", headers=_HDRS_MEM,
                    json={"agent_id": "ag-ctx-T38"})
    assert r.status_code == 200
    body = r.json()
    assert body["advisory_only"] is True
    data = body["data"]
    assert "episodic"   in data
    assert "semantic"   in data
    assert "procedural" in data
    assert "graph"      in data   # fechamento 1: graph sempre presente
    assert any(e["agent_id"] == "ag-ctx-T38" for e in data["episodic"])


# =============================================================================
# MACROBLOCO C — reflection_engine + build_agent integrado (T39–T46)
# =============================================================================

from memory_service.reflection_engine import (
    consolidate_signals,
    update_pattern_score,
    run_reflection,
)
from memory_service.storage import list_reflection_signals


# T39 — consolidate_signals: conta eventos → semantic_facts gravadas
def test_T39_consolidate_signals_writes_semantic_facts():
    sf = _make_mem_sf()
    insert_episodic_event(sf, "ag", "applied", "ok")
    insert_episodic_event(sf, "ag", "applied", "ok2")
    insert_episodic_event(sf, "ag", "error",   "falhou")
    counts = consolidate_signals(sf, agent_id="ag")
    assert counts["applied"] == 2
    assert counts["error"]   == 1
    facts = list_semantic_facts(sf, category="reflection_signal")
    keys = {f["key"] for f in facts}
    assert "applied_ag" in keys
    assert "error_ag"   in keys
    meta = list_semantic_facts(sf, category="reflection_meta")
    assert any("last_reflection_ag" in f["key"] for f in meta)


# T40 — update_pattern_score: clamp [0,1]; NÃO altera usage_count
def test_T40_update_pattern_score_clamp_sem_usage_count():
    sf = _make_mem_sf()
    upsert_procedural_pattern(sf, "pat-score", "desc", ["s"], success_rate=0.5)
    new_rate = update_pattern_score(sf, "pat-score", 0.3)
    assert abs(new_rate - 0.8) < 1e-6
    # clamp ao máximo
    assert update_pattern_score(sf, "pat-score", 0.5) == 1.0
    # clamp ao mínimo
    assert update_pattern_score(sf, "pat-score", -2.0) == 0.0
    # pattern inexistente → None
    assert update_pattern_score(sf, "inexistente", 0.1) is None
    # usage_count não é alterado pela reflexão
    patterns = list_procedural_patterns(sf, name="pat-score")
    assert patterns[0]["usage_count"] == 0


# T41 — run_reflection: escopo por agente + global
def test_T41_run_reflection_escopado():
    sf = _make_mem_sf()
    insert_episodic_event(sf, "ag-scoped", "applied", "missao ok")
    insert_episodic_event(sf, "ag-scoped", "error",   "missao falhou")
    insert_episodic_event(sf, "ag-outro",  "applied", "nao deve contar")

    # escopo do agente — 2 eventos
    result = run_reflection(sf, agent_id="ag-scoped")
    assert result["advisory_only"] is True
    data = result["data"]
    assert data["scope"] == "ag-scoped"
    assert data["total_events_analyzed"] == 2
    assert "signal_counts"       in data
    assert "patterns_adjusted"   in data

    # global — 3 eventos
    result_global = run_reflection(sf)
    assert result_global["data"]["scope"] == "global"
    assert result_global["data"]["total_events_analyzed"] == 3


# T42 — build_agent_context: procedural ranqueado por success_rate DESC
def test_T42_build_agent_context_procedural_ranked():
    sf = _make_mem_sf()
    upsert_procedural_pattern(sf, "pat-low",  "d", ["s"], success_rate=0.1)
    upsert_procedural_pattern(sf, "pat-high", "d", ["s"], success_rate=0.9)
    upsert_procedural_pattern(sf, "pat-mid",  "d", ["s"], success_rate=0.5)
    gw = RetrievalGateway(sf)
    ctx = gw.build_agent_context("ag3")
    procedural = ctx["data"]["procedural"]
    rates = [p["success_rate"] for p in procedural]
    assert rates == sorted(rates, reverse=True)


# T43 — build_agent_context: reflection_summary com sinais escopados + fallback global
def test_T43_build_agent_context_reflection_summary_scoped_fallback():
    sf = _make_mem_sf()
    upsert_procedural_pattern(sf, "pp-a", "d", ["s"], success_rate=0.8)
    # Sinal escopado para "ag-scope"
    upsert_semantic_fact(sf, "reflection_signal", "applied_ag-scope", "5",
                         source="reflection_engine")
    # Sinal global
    upsert_semantic_fact(sf, "reflection_signal", "error_global", "10",
                         source="reflection_engine")
    gw = RetrievalGateway(sf)

    # Agente com sinal específico → retorna sinal escopado
    ctx_scoped = gw.build_agent_context("ag-scope")
    rs = ctx_scoped["data"]["reflection_summary"]
    assert any("ag-scope" in s["signal"] for s in rs["top_signals"])

    # Agente sem sinal específico → fallback global
    ctx_fallback = gw.build_agent_context("ag-sem-sinal")
    rs_fb = ctx_fallback["data"]["reflection_summary"]
    assert any("global" in s["signal"] for s in rs_fb["top_signals"])


# T44 — list_reflection_signals: guardrail underscore — match exato via substr/length
def test_T44_list_reflection_signals_exact_scope_no_wildcard():
    sf = _make_mem_sf()
    # Chave com sufixo "ag" (sem underscore no scope)
    upsert_semantic_fact(sf, "reflection_signal", "applied_ag",     "3", source="r")
    # Chave com sufixo "ag-x" — NÃO deve ser retornada ao buscar scope="ag"
    upsert_semantic_fact(sf, "reflection_signal", "applied_ag-x",   "5", source="r")
    # Chave com sufixo "xag" — NÃO deve ser retornada (sem underscore antes)
    upsert_semantic_fact(sf, "reflection_signal", "applied_xag",    "2", source="r")
    # Chave global separada
    upsert_semantic_fact(sf, "reflection_signal", "applied_global",  "9", source="r")

    scoped = list_reflection_signals(sf, scope="ag")
    keys = {s["signal"] for s in scoped}
    assert "applied_ag"    in keys         # match exato
    assert "applied_ag-x"  not in keys     # diferente
    assert "applied_xag"   not in keys     # sem separador '_' antes de 'ag'
    assert "applied_global" not in keys    # scope diferente


# ---------------------------------------------------------------------------
# T45–T46 — Integração de endpoint (requer servidor em http://127.0.0.1:37777)
# ---------------------------------------------------------------------------

def test_T45_endpoint_reflect_run():
    r = _httpx.post(f"{_BASE_MEM}/memory/reflect/run",
                    headers=_HDRS_MEM, json={"agent_id": None})
    assert r.status_code == 200
    body = r.json()
    assert body["advisory_only"] is True
    data = body["data"]
    assert "signal_counts"         in data
    assert "patterns_adjusted"     in data
    assert "total_events_analyzed" in data


def test_T46_endpoint_agent_build_context():
    # Criar agente
    r_ag = _httpx.post(f"{_BASE_MEM}/agents", headers=_HDRS_MEM, json={
        "name": "ag-build-ctx-T46", "role": "tester",
        "system_prompt": "Agente de teste MACROBLOCO C",
    })
    assert r_ag.status_code == 201
    agent_id = r_ag.json()["id"]

    r = _httpx.get(f"{_BASE_MEM}/agents/{agent_id}/build-context", headers=_HDRS_MEM)
    assert r.status_code == 200
    body = r.json()
    assert body["advisory_only"] is True
    assert body["agent_id"]   == agent_id
    assert body["agent_name"] == "ag-build-ctx-T46"
    memory = body["memory"]
    assert "episodic"           in memory
    assert "semantic"           in memory
    assert "procedural"         in memory
    assert "graph"              in memory
    assert "reflection_summary" in memory


def test_T47_endpoint_build_context_agente_inexistente():
    r = _httpx.get(f"{_BASE_MEM}/agents/id-nao-existe/build-context",
                   headers=_HDRS_MEM)
    assert r.status_code == 404
