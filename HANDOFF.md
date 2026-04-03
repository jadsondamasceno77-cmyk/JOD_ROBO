# HANDOFF — X-Mom v5.0
**Data:** 2026-04-02 | **Ambiente:** WSL2 Linux | **Porta:** 37779

---

## Estado do sistema

```
$ curl http://localhost:37779/health
{"status":"ok","version":"2.0","squads":14,"agentes":188}

$ sudo systemctl status jod-robo-mae
● Active: active (running) — PID principal: python3 uvicorn robo_mae_api:app :37779
```

---

## Arquivos criados/modificados nesta sessão

### `xmom_bus.py` _(novo)_
Roteador local zero-LLM que substitui todas as chamadas `route_llm` (Groq).
- `route_local(message, squads)` → `(squad_slug, score)` — inclui social-squad
- `detect_intent_local(message)` → detecta `create_post` antes do fluxo original
- `SOCIAL_SQUAD` dict injetado em `SQUADS` na inicialização

### `xmom_state.py` _(novo)_
Key-value persistente em SQLite (`jod_robo.db`, tabela `xmom_state`).
```python
state_set(key, value)       # INSERT OR UPDATE
state_get(key, default=None) # retorna valor ou default
state_del(key)              # remove silenciosamente
state_all()                 # dict completo
```

### `robo_mae.py` _(modificado)_
| Mudança | Detalhe |
|---------|---------|
| `import xmom_bus` | roteamento local |
| `import xmom_state` | state persistente |
| `social-squad` injetado em SQUADS | 13 → 14 squads |
| `_tool_create_post(message, session_id)` | gera post via LLM, salva `.md` |
| intent `create_post` em detect_intent | via xmom_bus.detect_intent_local |
| intent `create_post` em execute_intent | chama _tool_create_post |
| `route_llm` substituído | xmom_bus.route_local (3 pontos) |
| `GLOBAL_OUTPUT_PATH` | `/home/jod_robo/outputs/` |

---

## `_tool_create_post` — contrato

```python
async def _tool_create_post(message: str, session_id: str) -> dict:
    # 1. load_memory(session_id)
    # 2. consult("social-squad", prompt_instagram, mem)
    # 3. salva /home/jod_robo/outputs/post_YYYYMMDD_HHMMSS.md
    # 4. save_memory(...)
    # Retorna: {"squad", "chief", "path", "content"}
```

---

## Teste de validação executado

```bash
# 1. Health
curl http://localhost:37779/health
# {"status":"ok","version":"2.0","squads":14,"agentes":188}

# 2. Roteamento instagram → social-squad (sem erro 500)
curl -X POST http://localhost:37779/chat \
  -H "Content-Type: application/json" \
  -H "x-jod-token: jod_robo_trust_2026_secure" \
  -d '{"message":"instagram","session_id":"test-002"}'
# {"squad":"social-squad","chief":"social-chief","response":"...","session_id":"test-002"}

# 3. create_post com save de arquivo
curl -X POST http://localhost:37779/chat \
  -H "Content-Type: application/json" \
  -H "x-jod-token: jod_robo_trust_2026_secure" \
  -d '{"message":"crie um post para instagram da minha marca de roupas fitness","session_id":"test-001"}'
# squad: "social-squad" ✓
# response inclui: /home/jod_robo/outputs/post_20260402_143156.md ✓
```

---

## Squads ativos (14)

`traffic-masters` · `copy-squad` · `brand-squad` · `data-squad` · `design-squad`
`hormozi-squad` · `storytelling` · `movement` · `cybersecurity` · `claude-code-mastery`
`c-level-squad` · `advisory-board` · `n8n-squad` · **`social-squad`** _(novo)_

---

## Serviço systemd

```
Unit:    /etc/systemd/system/jod-robo-mae.service
Start:   sudo systemctl start jod-robo-mae
Restart: sudo systemctl restart jod-robo-mae
Logs:    sudo journalctl -u jod-robo-mae -f
```

---

## Próximos passos

1. Inserir `social-chief` na tabela `agents` do SQLite com persona de social media manager
2. Usar `xmom_state` para cachear últimas sessões e preferências de squad
3. Adicionar parâmetro `platform` em `_tool_create_post` (instagram/tiktok/linkedin)
4. Remover função `route_llm` (dead code — não é mais chamada)
