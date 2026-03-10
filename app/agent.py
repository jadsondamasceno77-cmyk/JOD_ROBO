import os, logging, subprocess, tempfile, json
from groq import AsyncGroq

logger = logging.getLogger("jod_robo")
MEMORY_FILE = os.path.join(os.path.dirname(__file__), "..", "memory.json")

def load_memory():
    try:
        if os.path.exists(MEMORY_FILE): return json.load(open(MEMORY_FILE))
    except: pass
    return []

def save_memory(memory):
    try: json.dump(memory[-20:], open(MEMORY_FILE, "w"), ensure_ascii=False, indent=2)
    except: pass

class JODAgent:
    def __init__(self, name=None, system=None):
        self.client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY",""))
        self.model = "llama-3.3-70b-versatile"
        self.name = name or "JOD_ROBO"
        self.system = system or "Voce e o JOD_ROBO, agente executor. Responda em Portugues."
        self.memory = load_memory()
    async def think(self, text, context=None):
        msgs = [{"role":"system","content":self.system}]
        if context: msgs.append({"role":"system","content":"Contexto: "+context})
        for m in self.memory[-6:]: msgs.append(m)
        msgs.append({"role":"user","content":text})
        r = await self.client.chat.completions.create(model=self.model,messages=msgs,max_tokens=1024)
        reply = r.choices[0].message.content
        self.memory.append({"role":"user","content":text})
        self.memory.append({"role":"assistant","content":reply})
        save_memory(self.memory)
        return reply
    async def execute_python(self, code):
        with tempfile.NamedTemporaryFile(mode="w",suffix=".py",delete=False) as f:
            f.write(code); tmp = f.name
        try:
            r = subprocess.run(["python3",tmp],capture_output=True,text=True,timeout=30)
            return {"stdout":r.stdout,"stderr":r.stderr,"success":r.returncode==0}
        except Exception as e: return {"error":str(e),"success":False}
        finally: os.unlink(tmp)
    async def analyze_site(self, url):
        return await self.think("Analise o site "+url)

class CEOAgent(JODAgent):
    def __init__(self):
        super().__init__(name="ELI-CEO",system="Voce e o CEO da ELI, agencia de IA. Estrategico, direto. Responda em portugues.")

agent = JODAgent()
ceo = CEOAgent()
