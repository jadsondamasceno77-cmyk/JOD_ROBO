import os, asyncio, logging, subprocess, tempfile
from typing import Optional
from groq import AsyncGroq

logger = logging.getLogger(__name__)

class JODAgent:
    def __init__(self):
        self.client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY",""))
        self.model = "meta-llama/llama-4-scout-17b-16e-instruct"
        self.name = os.getenv("AGENT_NAME","JOD_ROBO")
        self.role = os.getenv("AGENT_ROLE","executor")
        self.memory = []
        self.system = os.getenv("AGENT_SYSTEM_PROMPT","Você é o JOD_ROBO, agente executor inteligente. Responda em Português.")

    async def think(self, text: str, context: Optional[str]=None) -> str:
        msgs = [{"role":"system","content":self.system}]
        if context: msgs.append({"role":"system","content":f"Contexto: {context}"})
        for m in self.memory[-10:]: msgs.append(m)
        msgs.append({"role":"user","content":text})
        r = await self.client.chat.completions.create(model=self.model,messages=msgs,max_tokens=2048)
        reply = r.choices[0].message.content
        self.memory.append({"role":"user","content":text})
        self.memory.append({"role":"assistant","content":reply})
        return reply

    async def execute_python(self, code: str) -> dict:
        with tempfile.NamedTemporaryFile(mode='w',suffix='.py',delete=False) as f:
            f.write(code); tmp=f.name
        try:
            r = subprocess.run(["python3",tmp],capture_output=True,text=True,timeout=30)
            return {"stdout":r.stdout,"stderr":r.stderr,"success":r.returncode==0}
        except Exception as e:
            return {"error":str(e),"success":False}
        finally:
            os.unlink(tmp)

    async def analyze_site(self, url: str) -> str:
        prompt = f"Faça uma análise completa do site {url}: pontos fortes, fracos, gargalos, score 0-10 e plano para torná-lo obsoleto."
        return await self.think(prompt)

    def clone(self, name: str, role: str, prompt: str) -> "JODAgent":
        c = JODAgent()
        c.name=name; c.role=role; c.system=prompt; c.client=self.client
        return c

agent = JODAgent()
