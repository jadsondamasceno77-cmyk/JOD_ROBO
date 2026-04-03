# X-Mom v5.0 — Handoff Document
**Data:** 2026-04-02
**Estado:** PRODUÇÃO ativa na porta 37779

---

## Arquitetura Atual

```
robo_mae_api.py  (FastAPI :37779)
       │
       └── robo_mae.py  (processo principal)
               ├── detect_intent()        ← keywords locais + xmom_bus
               ├── execute_intent()       ← factory / browser / n8n / create_post / save_file
               ├── route()                ← keyword scoring (SQUADS dict)
               ├── xmom_bus.route_local() ← fallback local sem LLM (substitui route_llm)
               ├── consult_parallel()     ← Groq llama-3.3-70b (n=2) + OpenRouter fallback
               └── _tool_create_post()    ← NEW: gera post, salva em /home/jod_robo/outputs/
```

---

## Mudanças desta sessão

### 1. `xmom_bus.py` (novo arquivo)
- Roteador local puro — zero chamadas LLM
- `route_local(message, squads)` → `(squad_slug, score)`
  - Combina SQUADS originais + SOCIAL_SQUAD
  - Fallback heurístico: msg curta → `c-level-squad`, longa → `advisory-board`
- `detect_intent_local(message)` → `dict | None`
  - Detecta `create_post` antes de `detect_intent` original
- `SOCIAL_SQUAD` dict injetado em `SQUADS` na inicialização do robo_mae

### 2. `robo_mae.py` — mudanças

| Ponto | Antes | Depois |
|-------|-------|--------|
| `route_llm` (score=0) | chamada Groq | `xmom_bus.route_local()` |
| `route_llm` (auto-correção) | chamada Groq | `xmom_bus.route_local()` |
| `save_file` fallback | chamada Groq | `xmom_bus.route_local()` |
| SQUADS | 13 squads | 14 squads (+social-squad) |
| `_tool_create_post` | inexistente | implementado |
| intent `create_post` | inexistente | `detect_intent` + `execute_intent` |
| `GLOBAL_OUTPUT_PATH` | `XMOM_V5/outputs/` | `/home/jod_robo/outputs/` |

### 3. `_tool_create_post(message, session_id)` → `dict`
```python
# Fluxo:
# 1. load_memory(session_id)
# 2. consult("social-squad", prompt_instagram, mem)
# 3. salva em /home/jod_robo/outputs/post_YYYYMMDD_HHMMSS.md
# 4. save_memory(...)
# Retorna: {squad, chief, path, content}
```

---

## Squads ativos (14)

| Slug | Chief |
|------|-------|
| traffic-masters | traffic-chief |
| copy-squad | copy-chief |
| brand-squad | brand-chief |
| data-squad | data-chief |
| design-squad | design-chief |
| hormozi-squad | hormozi-chief |
| storytelling | story-chief |
| movement | movement-chief |
| cybersecurity | cyber-chief |
| claude-code-mastery | claude-mastery-chief |
| c-level-squad | vision-chief |
| advisory-board | board-chair |
| n8n-squad | n8n-chief |
| **social-squad** *(novo)* | social-chief |

---

## Endpoints da API

| Método | Path | Auth | Descrição |
|--------|------|------|-----------|
| GET | `/health` | - | Status + versão + contagem de squads |
| POST | `/chat` | `x-jod-token` | Roteamento + consulta + intent |
| GET | `/squads` | - | Lista todos os squads |
| GET | `/agents` | - | Lista agentes do Factory |
| GET | `/audit` | - | World state + squad performance |
| GET | `/` | - | UI HTML |

---

## Teste de validação executado

```bash
# Health
curl http://localhost:37779/health
# → {"status":"ok","version":"2.0","squads":14,"agentes":188}

# Instagram → social-squad + arquivo salvo
curl -X POST http://localhost:37779/chat \
  -H "Content-Type: application/json" \
  -H "x-jod-token: jod_robo_trust_2026_secure" \
  -d '{"message":"crie um post para instagram da minha marca de roupas fitness","session_id":"test-001"}'
# → squad: "social-squad", chief: "social-chief"
# → response inclui path: /home/jod_robo/outputs/post_20260402_143156.md
```

---

## Savings de tokens (xmom_bus)

Cada mensagem que caia em `route_llm` consumia ~200-400 tokens (Groq llama-3.3-70b).
Com `xmom_bus.route_local()`, esse custo é **zero** para routing e intent detection.
LLM só é chamado para `consult()` (geração de conteúdo) e `evaluate_output()`.

---

## Arquivos relevantes

| Arquivo | Função |
|---------|--------|
| `robo_mae.py` | Core: routing, intent, consulta, memory |
| `robo_mae_api.py` | FastAPI wrapper (porta 37779) |
| `xmom_bus.py` | Roteador local zero-LLM *(novo)* |
| `agente_browser.py` | Navegação web |
| `agente_n8n.py` | Criação de workflows n8n |
| `world_state.json` | Persistência de estado entre sessões |
| `jod_robo.db` | Performance por squad (SQLite) |
| `/home/jod_robo/outputs/` | Posts e arquivos gerados *(novo)* |
| `memory/conversations.jsonl` | Histórico de conversas |

---

## Próximos passos sugeridos

1. **social-chief no DB**: inserir agente `social-chief` na tabela `agents` com persona de social media manager para enriquecer as respostas
2. **`_tool_create_post` multi-rede**: adicionar parâmetro `platform` (instagram/tiktok/linkedin) com prompts específicos por plataforma
3. **Avaliação de posts**: integrar `evaluate_output()` no fluxo `create_post` para score automático
4. **`route_llm` remoção total**: a função ainda existe mas não é mais chamada — pode ser removida em cleanup futuro
