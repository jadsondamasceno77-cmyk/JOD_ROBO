"""Testes unitários para jod_brain.io."""
import sys, os, pytest
sys.path.insert(0, "/home/wsl/JOD_ROBO")
from jod_brain.io import write_file

def test_write_file_cria_arquivo(tmp_path):
    ok = write_file(str(tmp_path), "scripts/hello.py", "print('hello')")
    assert ok is True
    assert (tmp_path / "scripts" / "hello.py").exists()

def test_write_file_cria_diretorios(tmp_path):
    ok = write_file(str(tmp_path), "agents/sub/agent.py", "x = 1")
    assert ok is True
    assert (tmp_path / "agents" / "sub" / "agent.py").exists()

def test_write_file_bloqueia_path_traversal(tmp_path):
    ok = write_file(str(tmp_path), "../../../etc/cron", "malware")
    assert ok is False

def test_write_file_bloqueia_python_invalido(tmp_path):
    ok = write_file(str(tmp_path), "scripts/bad.py", "print('broken'")
    assert ok is False

def test_write_file_bloqueia_extensao_proibida(tmp_path):
    ok = write_file(str(tmp_path), "scripts/evil.exe", "malware")
    assert ok is False

def test_write_file_path_vazio(tmp_path):
    ok = write_file(str(tmp_path), "", "conteudo")
    assert ok is False

def test_write_file_conteudo_vazio(tmp_path):
    ok = write_file(str(tmp_path), "scripts/vazio.py", "")
    assert ok is False

def test_write_file_markdown(tmp_path):
    ok = write_file(str(tmp_path), "docs/readme.md", "# Título\n\nConteúdo.")
    assert ok is True

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
