"""Cliente LLM com fallback Groq → Ollama, retry e circuit breaker."""
import json, urllib.request, time, logging
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError

logger = logging.getLogger("jod.llm")

class LLMError(RuntimeError):
    """Falha em todas as tentativas de chamada ao LLM."""

def _do_groq(system: str, user_msg: str, api_key: str) -> str:
    payload = json.dumps({
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg}
        ],
        "max_tokens": 4096
    }).encode()
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "curl/7.88.1"
        }
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["choices"][0]["message"]["content"]

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def call_groq(system: str, user_msg: str, api_key: str) -> Optional[str]:
    """Chama Groq com retry exponencial.
    
    Args:
        system: System prompt.
        user_msg: Mensagem do usuário.
        api_key: Chave da API Groq.
    
    Returns:
        Resposta do modelo ou None se falhar.
    """
    try:
        result = _do_groq(system, user_msg, api_key)
        logger.info("Groq respondeu com sucesso")
        return result
    except Exception as e:
        logger.warning(f"Groq falhou: {e}")
        raise

def call_ollama(prompt: str, model: str = "llama3.2:1b", host: str = "http://127.0.0.1:11434") -> Optional[str]:
    """Chama Ollama local como fallback.
    
    Args:
        prompt: Prompt completo.
        model: Modelo Ollama a usar.
        host: URL base do Ollama.
    
    Returns:
        Resposta do modelo ou None se falhar.
    """
    try:
        payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
        req = urllib.request.Request(
            f"{host}/api/generate", data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=300) as r:
            result = json.load(r).get("response", "")
            logger.info("Ollama respondeu como fallback")
            return result
    except Exception as e:
        logger.error(f"Ollama falhou: {e}")
        return None

def parse_json(raw: str) -> Optional[dict]:
    """Parser JSON resiliente para respostas verbosas de LLMs.
    
    Args:
        raw: Texto bruto da resposta do LLM.
    
    Returns:
        Dict parseado ou None se não encontrar JSON válido.
    """
    clean = raw.strip()
    if clean.startswith("```"):
        clean = "\n".join(clean.split("\n")[1:-1])
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        depth = 0; start = -1
        for i, ch in enumerate(clean):
            if ch == "{":
                if depth == 0: start = i
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0 and start != -1:
                    try: return json.loads(clean[start:i+1])
                    except json.JSONDecodeError: start = -1
    return None
