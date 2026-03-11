import os, asyncio, logging, time
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jod_robo")
app = FastAPI(title="JOD_ROBO", version="3.0.0")
START_TIME = time.time()

@app.get("/health")
async def health():
    return {"status": "online", "version": "3.0.0", "uptime": round(time.time() - START_TIME, 2)}

@app.post("/execute")
async def execute(request: Request):
    try:
        body = await request.json()
        task = body.get("task", "")
        if not task:
            return JSONResponse(status_code=400, content={"error": "task vazia"})

        # Detecta se e conversa ou comando de criacao
        palavras_criacao = ["cria", "crie", "gera", "gere", "faz", "faca", "desenvolve",
                           "implementa", "constroi", "adiciona", "escreve", "build"]
        eh_criacao = any(p in task.lower() for p in palavras_criacao)

        if eh_criacao:
            # Modo criacao: executa jod_brain_main.py --apply
            proc = await asyncio.create_subprocess_shell(
                f'cd /home/wsl/JOD_ROBO && python3 /home/wsl/JOD_ROBO/jod_brain_main.py "{task}" --apply',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env={**os.environ, "GROQ_API_KEY": os.environ.get("GROQ_API_KEY", "")}
            )
            stdout, _ = await proc.communicate()
            return {"output": stdout.decode(), "mode": "criacao"}
        else:
            # Modo conversa: pergunta direta ao Groq
            import urllib.request, json
            api_key = os.environ.get("GROQ_API_KEY", "")
            payload = json.dumps({
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": "Voce e JOD, assistente pessoal de Jadson Damasceno. Seja direto, claro, sem ambiguidades. Jadson e autista com Asperger. Responda em portugues."},
                    {"role": "user", "content": task}
                ],
                "max_tokens": 2048
            }).encode()
            req = urllib.request.Request(
                "https://api.groq.com/openai/v1/chat/completions",
                data=payload,
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {api_key}",
                         "User-Agent": "curl/7.88.1"}
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                resp = json.load(r)
                resposta = resp["choices"][0]["message"]["content"]
            return {"output": resposta, "mode": "conversa"}

    except Exception as e:
        logger.error(f"Erro: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/", response_class=HTMLResponse)
async def ui():
    return open("/home/wsl/JOD_ROBO/app/ui.html").read()
