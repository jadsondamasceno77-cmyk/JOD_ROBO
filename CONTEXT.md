# CONTEXT.md — X-Mom v5.0 (documento vivo)
**Atualizado:** 2026-04-03 11:00:04
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
       └── jod_robo.db     agents(201) | agent_performance | semantic_memory(95)
```

---

## Banco de Dados (jod_robo.db)

| Tabela | Registros |
|--------|-----------|
| agents | 201 |
| semantic_memory | 95 |
| agent_performance | (ver abaixo) |
| xmom_events (pending) | 0 |

**Top squads por score:**
  brand-squad: score=8.0 calls=8
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

## Skills Marketplace (LobeHub) — 2026-04-03

**Instaladas via:** `npx -y @lobehub/market-cli skills install <skill> --agent claude-code`
**Diretório:** `.claude/skills/`
**Device ID:** `jod-robo-xmom-DESKTOP-SAS2R1U` | Client: `cli_dpFgUPIKmAYpsAR4vANv1ZM5dlNVknJp`

### ✅ Instaladas com sucesso (52/56)

| Skill | Binários setup | Env vars necessários |
|-------|---------------|---------------------|
| openclaw-openclaw-1password | `op` (brew, macOS only) | — |
| openclaw-openclaw-acp-router | — | — |
| openclaw-openclaw-blogwatcher | `blogwatcher` (go, requer go>=1.24) | — |
| openclaw-openclaw-blucli | `blu` (go, requer go>=1.24) | — |
| openclaw-openclaw-canvas | — | — |
| openclaw-openclaw-clawhub | ✅ `clawhub` instalado (npm) | — |
| openclaw-openclaw-coding-agent | ✅ `claude` disponível | — |
| openclaw-openclaw-diffs | — | — |
| openclaw-openclaw-discord | — | `channels.discord.token` (openclaw config) |
| openclaw-openclaw-gemini | `gemini` (brew, macOS only) | — |
| openclaw-openclaw-gh-issues | ✅ `gh` + `curl` + `git` instalados | `GH_TOKEN` (adicionar ao .env) |
| openclaw-openclaw-github | ✅ `gh` instalado | `gh auth login` pendente |
| openclaw-openclaw-goplaces | `goplaces` (brew, macOS only) | `GOOGLE_PLACES_API_KEY` ⚠️ |
| openclaw-openclaw-healthcheck | — | — |
| openclaw-openclaw-himalaya | `himalaya` (brew, macOS only) | — |
| openclaw-openclaw-imsg | `imsg` (brew, macOS only) | — |
| openclaw-openclaw-lobster | — | — |
| openclaw-openclaw-local-places | ✅ `uv` instalado | `GOOGLE_PLACES_API_KEY` ⚠️ |
| openclaw-openclaw-mcporter | ✅ `mcporter` instalado (npm) | — |
| openclaw-openclaw-model-usage | `codexbar` (brew cask, macOS only) | — |
| openclaw-openclaw-nano-banana-pro | ✅ `uv` instalado | `GEMINI_API_KEY` ⚠️ |
| openclaw-openclaw-nano-pdf | ✅ `nano-pdf` instalado (pip) | — |
| openclaw-openclaw-node-connect | — | — |
| openclaw-openclaw-notion | — | `NOTION_API_KEY` ⚠️ |
| openclaw-openclaw-obsidian | `obsidian-cli` (brew, macOS only) | — |
| openclaw-openclaw-openai-image-gen | ✅ `python3` disponível | `OPENAI_API_KEY` ⚠️ |
| openclaw-openclaw-openai-whisper | ✅ `whisper` instalado (pip) | — |
| openclaw-openclaw-openclaw-ghsa-maintainer | — | — |
| openclaw-openclaw-openclaw-parallels-smoke | — | — |
| openclaw-openclaw-openclaw-pr-maintainer | — | — |
| openclaw-openclaw-openclaw-release-maintainer | — | — |
| openclaw-openclaw-openclaw-test-heap-leaks | — | — |
| openclaw-openclaw-ordercli | `ordercli` (fonte desconhecida) | — |
| openclaw-openclaw-parallels-discord-roundtrip | — | — |
| openclaw-openclaw-peekaboo | `peekaboo` (brew, macOS only) | — |
| openclaw-openclaw-prose | — | — |
| openclaw-openclaw-sag | `sag` (bin pendente) | `ELEVENLABS_API_KEY` ⚠️ |
| openclaw-openclaw-security-triage | — | — |
| openclaw-openclaw-session-logs | ✅ `jq` + `rg` instalados | — |
| openclaw-openclaw-sherpa-onnx-tts | — | `SHERPA_ONNX_RUNTIME_DIR` + `SHERPA_ONNX_MODEL_DIR` ⚠️ |
| openclaw-openclaw-skill-creator | — | — |
| openclaw-openclaw-slack | — | `channels.slack` (openclaw config) |
| openclaw-openclaw-sonoscli | `sonos` (fonte pendente) | — |
| openclaw-openclaw-spotify-player | `spogo` (fonte pendente) | — |
| openclaw-openclaw-summarize | `summarize` (fonte pendente) | — |
| openclaw-openclaw-tmux | ✅ `tmux` já instalado | — |
| openclaw-openclaw-trello | ✅ `jq` instalado | `TRELLO_API_KEY` + `TRELLO_TOKEN` ⚠️ |
| openclaw-openclaw-video-frames | ✅ `ffmpeg` instalado | — |
| openclaw-openclaw-voice-call | — | `plugins.entries.voice-call.enabled` (openclaw config) |
| openclaw-openclaw-wacli | `wacli` (fonte pendente) | — |
| openclaw-openclaw-weather | ✅ `curl` disponível | — |
| openclaw-openclaw-xurl | `xurl` (fonte pendente) | — |

### ❌ Falhou — Skill not found no marketplace (4/56)

| Skill | Motivo |
|-------|--------|
| openclaw-openclaw-pr-maintainer | Removida do marketplace (use `openclaw-openclaw-openclaw-pr-maintainer`) |
| openclaw-openclaw-release-maintainer | Removida do marketplace (use `openclaw-openclaw-openclaw-release-maintainer`) |
| openclaw-openclaw-ghsa-maintainer | Removida do marketplace (use `openclaw-openclaw-openclaw-ghsa-maintainer`) |
| openclaw-openclaw-openclaw-sag | Removida do marketplace (use `openclaw-openclaw-sag`) |

> As 4 skills com falha têm equivalentes instalados: os prefixos `openclaw-openclaw-openclaw-*` são as versões correntes.

### ⚠️ Env vars pendentes (adicionar ao .env)

```bash
# Adicionar em /home/jod_robo/XMOM_V5/.env conforme disponível:
GOOGLE_PLACES_API_KEY=   # goplaces + local-places
GEMINI_API_KEY=          # nano-banana-pro
NOTION_API_KEY=          # notion
OPENAI_API_KEY=          # openai-image-gen
TRELLO_API_KEY=          # trello
TRELLO_TOKEN=            # trello
ELEVENLABS_API_KEY=      # sag (voice synthesis)
GH_TOKEN=                # gh-issues (GitHub Personal Access Token)
# SHERPA_ONNX_RUNTIME_DIR + SHERPA_ONNX_MODEL_DIR — instalar sherpa-onnx manualmente
```

---

## Outputs Gerados

- Arquivos em /home/jod_robo/outputs/: 5 arquivos
- Últimos 5: `/home/jod_robo/outputs/test_xmom_suite.md /home/jod_robo/outputs/test_s5.md /home/jod_robo/outputs/demo_CLIENTETESTE.md /home/jod_robo/outputs/post_20260402_145116.md /home/jod_robo/outputs/post_20260402_143156.md `

---

## Git Log (últimos 10)

```
1999297 CAMADA 1 infraestrutura 10/10
997e3f2 backup auto 2026-04-03 00:33 — X-Mom v5.0
f6990a8 X-Mom v5.0 AOS — score 100/100
d798812 
```

## Arquivos modificados recentemente

```
CONTEXT.md
__pycache__/robo_mae.cpython-310.pyc
__pycache__/robo_mae_api.cpython-310.pyc
__pycache__/xmom_bus.cpython-310.pyc
__pycache__/xmom_semantic.cpython-310.pyc
__pycache__/xmom_state.cpython-310.pyc
jod_robo.db
memory/conversations.jsonl
world_state.json
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
*Gerado automaticamente por update_context.sh — 2026-04-03 11:00:04*
