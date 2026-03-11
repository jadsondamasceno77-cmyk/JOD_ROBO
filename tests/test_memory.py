"""Testes unitários para jod_brain.memory."""
import sys, os, json, pytest, tempfile
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
