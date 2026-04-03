# CONTEXT.md — X-Mom v5.0 (documento vivo)
**Atualizado:** 2026-04-03 00:00:04
**Script:** update_context.sh

---

## Estado dos Serviços

| Serviço | Status | Porta |
|---------|--------|-------|
| jod-robo-mae | active | 37779 |
| n8n | active | 5678 |
| jod-factory | active | 37777 |

**Health check:** `{"status":"ok","version":"2.0","squads":14,"agentes":188}`

---

## Arquitetura Atual

```
robo_mae_api.py  (FastAPI :37779)
       │
       └── robo_mae.py  (núcleo v5.0 — GAPs 1-6 fechados)
               ├── detect_intent()          keywords + xmom_bus + GAPs 1,4,5
               ├── execute_intent()         factory/browser/n8n/tools/orchestrate
               ├── _tool_run_python()       GAP 1 — sandbox AST
               ├── _tool_send_webhook()     GAP 4
               ├── _tool_read_file()        GAP 4
               ├── _tool_write_file()       GAP 4
               ├── _tool_call_api()         GAP 4
               ├── multi_squad_consult()    GAP 5 — orquestração paralela
               ├── evaluate_output()        GAP 6 — score < 7 → retry
               ├── save_memory()            → feed_semantic_memory (GAP 2)
               ├── consult_parallel()       Groq llama-3.3-70b + OpenRouter cb
               └── process()               loop principal com evaluate+retry
       │
       ├── xmom_bus.py     roteamento local + pub/sub task queue
       ├── xmom_state.py   key-value SQLite
       ├── xmom_semantic.py feed + search semantic_memory (GAP 2)
       └── jod_robo.db     agents(201) | agent_performance | semantic_memory(40)
```

---

## Banco de Dados (jod_robo.db)

| Tabela | Registros |
|--------|-----------|
| agents | 201 |
| semantic_memory | 40 |
| agent_performance | (ver abaixo) |
| xmom_events (pending) | 0 |

**Top squads por score:**
  brand-squad: score=8.0 calls=3
  copy-squad: score=7.5 calls=2
  traffic-masters: score=7.0 calls=0
  data-squad: score=7.0 calls=0
  design-squad: score=7.0 calls=0

---

## Squads Ativos (14)

`traffic-masters` · `copy-squad` · `brand-squad` · `data-squad` · `design-squad`
`hormozi-squad` · `storytelling` · `movement` · `cybersecurity` · `claude-code-mastery`
`c-level-squad` · `advisory-board` · `n8n-squad` · `social-squad`

---

## GAPs — Estado

| GAP | Descrição | Status |
|-----|-----------|--------|
| GAP 1 | Sandbox Python (tool_run_python + AST check) | ✅ FECHADO |
| GAP 2 | Pipeline semantic_memory após cada output | ✅ FECHADO |
| GAP 3 | populate_agents.py — persona/desc/cap 188 agentes | ✅ FECHADO |
| GAP 4 | tool_send_webhook / tool_read_file / tool_write_file / tool_call_api | ✅ FECHADO |
| GAP 5 | Orquestração multi-agente (multi_squad_consult + pub/sub) | ✅ FECHADO |
| GAP 6 | evaluate_output no loop — score < 7 → retry automático | ✅ FECHADO |

---

## Outputs Gerados

- Arquivos em /home/jod_robo/outputs/: 5 arquivos
- Últimos 5: `/home/jod_robo/outputs/test_xmom_suite.md /home/jod_robo/outputs/test_s5.md /home/jod_robo/outputs/demo_CLIENTETESTE.md /home/jod_robo/outputs/post_20260402_145116.md /home/jod_robo/outputs/post_20260402_143156.md `

---

## Git Log (últimos 10)

```
d798812 
```

## Arquivos modificados recentemente

```
.gitignore
agente_browser.py
agente_n8n.py
agente_n8n_externo.py
jod_robo.db
robo_mae.py
robo_mae_api.py
ui.html
```

---

## Próximos Comandos Prontos

```bash
# Testar sandbox
curl -X POST http://localhost:37779/chat \
  -H "x-jod-token: jod_robo_trust_2026_secure" \
  -H "Content-Type: application/json" \
  -d '{"message":"execute python\nprint(sum(range(10)))","session_id":"test"}'

# Testar orquestração
curl -X POST http://localhost:37779/chat \
  -H "x-jod-token: jod_robo_trust_2026_secure" \
  -H "Content-Type: application/json" \
  -d '{"message":"orquestre copy-squad e brand-squad: crie uma identidade para startup fintech","session_id":"orch-test"}'

# Testar webhook
curl -X POST http://localhost:37779/chat \
  -H "x-jod-token: jod_robo_trust_2026_secure" \
  -H "Content-Type: application/json" \
  -d '{"message":"envie webhook para https://httpbin.org/post","session_id":"wh-test"}'

# Popular agentes
cd /home/jod_robo/XMOM_V5 && python3 populate_agents.py

# Atualizar contexto
/home/jod_robo/update_context.sh

# Ver logs do serviço
sudo journalctl -u jod-robo-mae -f --no-pager
```

---

## Comandos de Manutenção

```bash
# Restart serviço
sudo systemctl restart jod-robo-mae

# Ver tarefas pendentes no bus
python3 -c "import sys; sys.path.insert(0,'/home/jod_robo/XMOM_V5'); import xmom_bus; print(xmom_bus.pending_count())"

# Verificar semantic_memory
python3 -c "
import sys; sys.path.insert(0,'/home/jod_robo/XMOM_V5')
from xmom_semantic import search_semantic
print(search_semantic('instagram post', limit=3))
"
```

---
*Gerado automaticamente por update_context.sh — 2026-04-03 00:00:04*
