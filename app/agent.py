import os
import asyncio
import logging
import subprocess
import tempfile
from groq import AsyncGroq

logger = logging.getLogger("jod_robo")

class JODAgent:
    def __init__(self, name=None, role=None, system=None):
        self.client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY", ""))
        self.model = "meta-llama/llama-4-scout-17b-16e-instruct"
        self.name = name or os.getenv("AGENT_NAME", "JOD_ROBO")
        self.role = role or os.getenv("AGENT_ROLE", "executor")
        self.system = system or os.getenv("AGENT_SYSTEM_PROMPT", "Você é o JOD_ROBO, agente executor inteligente. Responda em Português.")
        self.memory = []

    async def think(self, text, context=None):
        msgs = [{"role": "system", "content": self.system}]
        if context:
            msgs.append({"role": "system", "content": "Contexto: " + context})
        for m in self.memory[-10:]:
            msgs.append(m)
        msgs.append({"role": "user", "content": text})
        r = await self.client.chat.completions.create(model=self.model, messages=msgs, max_tokens=2048)
        reply = r.choices[0].message.content
        self.memory.append({"role": "user", "content": text})
        self.memory.append({"role": "assistant", "content": reply})
        return reply

    async def execute_python(self, code):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            tmp = f.name
        try:
            r = subprocess.run(["python3", tmp], capture_output=True, text=True, timeout=30)
            return {"stdout": r.stdout, "stderr": r.stderr, "success": r.returncode == 0}
        except Exception as e:
            return {"error": str(e), "success": False}
        finally:
            os.unlink(tmp)

    async def analyze_site(self, url):
        prompt = "Faça análise completa do site " + url + ": pontos fortes, fracos, score 0-10 e plano para torná-lo obsoleto."
        return await self.think(prompt)

    def clone(self, name, role, system):
        return JODAgent(name=name, role=role, system=system)

class CEOAgent(JODAgent):
    def __init__(self):
        super().__init__(
            name="ELI-CEO",
            role="ceo",
            system="""Você é o agente CEO da ELI, agência de IA. 
Sua personalidade: estratégico, direto, orientado a resultados.
Você toma decisões de negócio, define prioridades e delega para os outros agentes.
Responda sempre em português, com clareza e autoridade executiva."""
        )

agent = JODAgent()
