# Estado Atual do Projeto — JOD_ROBO
**Atualizado em:** 2026-03-18 (MACROBLOCO E)

## Arquivos principais

| Arquivo | Papel |
|---|---|
| `main_fase2.py` | Core da API — FastAPI + SQLAlchemy + fila assíncrona |
| `jod_brain_main.py` | Loop com aprovação humana síncrona — human-in-the-loop, NÃO é autonomia real |
| `app/main.py` | Fachada REST para `jod_brain_main.py` (Railway) |
| `templates/finalizer_agent.json` | Template do Agente Finalizador |
| `templates/finalizer_manifest.json` | Manifesto padrão do Finalizador |
| `templates/guardian_agent.json` | Template do Agente Guardião |

## Fases fechadas com evidência runtime real

| Fase | Testes | Status |
|------|--------|--------|
| Finalizador — Agente 2 | 16 passed | 10/10 fechado (D-016) |
| Guardião — Agente 3 | 15 passed | 10/10 fechado (D-019) |
| B1 — stale attestation | 5 passed | 10/10 fechado (D-022) |
| B1.2 — veto E2E real do Guardião | 4 passed | 10/10 fechado (D-024) |
| P1 — serialização por target_path | 3 passed | aprovado (D-025) |
| Fase 1 — Recuperação real pós-queda | 8 passed | 10/10 fechado (D-036) |
| MACROBLOCO A — aprovação, retry, circuit breaker | 6 passed | fechado (D-037, commit d18c051) |
| MACROBLOCO B — memory_service | 16 passed | fechado (D-038, commit e1937a2) |
| MACROBLOCO C — reflection_engine + build_agent | 9 passed | fechado (D-039, commit 1fd2315) |
| MACROBLOCO D — watchdog autônomo + redespacho formal | 9 passed | fechado (D-040, commit 9f7d12e) |
| MACROBLOCO E — ts real nos logs JSON + CI remoto | 1+145 passed | fechado (D-041, D-042, commit pendente) |

## Regressão confirmada
- **145 passed, 0 failed** — última execução: 2026-03-18 (pós MACROBLOCO E)

## Estado de P2 e P3 — com ressalva

### P2 — Logs JSON + correlation_id
- **CERTIFICADO 10/10** — 2026-03-18 (D-041)
- `_JsonFormatter` produz `ts` com microsegundos reais: `2026-03-18T21:13:08.332157`
- Contrato travado por `test_json_formatter_ts_has_real_microseconds` em `test_b2_serialization_and_logs.py`

### P3 — CI/CD GitHub Actions
- **PENDENTE evidência remota** — push em andamento (D-042)
- Workflow corrigido: trigger inclui `padrão`, 13 arquivos de teste (145 testes), paths dinâmicos em todos os arquivos

## Robô-mãe
- **MVP IMPLEMENTADO E APROVADO** — 2026-03-17
- Módulo: `robo_mae/` (context, registry, executor, log, reporter, mission_control)
- Endpoint: `POST /missions/run` + `/missions/{id}/approval` + `/approve` + `/deny`
- Tabelas: `mission_log`, `mission_control`, `approval_requests`, `circuit_breaker`
- Decisões: D-030 a D-037

## Memory Service — MACROBLOCO B
- **IMPLEMENTADO E APROVADO** — 2026-03-18
- Módulo: `memory_service/` (policy_guard, migrate, storage, retrieval_gateway)
- Separado completamente de `robo_mae/` — sem contaminação do core crítico
- Contrato: memória cognitiva é advisory_only; policy_guard é barreira formal
- Tabelas: `episodic_events`, `semantic_facts`, `procedural_patterns`, `graph_nodes`, `graph_edges`
- Endpoints: 11 rotas `/memory/` (events, facts, patterns, graph/nodes, graph/edges, graph/neighbors, context, reflect)
- Testes: T23–T38 (11 unitários + 5 endpoint)
- Decisão: D-038

## Banco de dados
- SQLite em `jod_robo.db`
- Tabelas core: `agents`, `finalizer_manifests`, `finalizer_snapshots`, `finalizer_audit`, `guardian_audit`, `integration_audit`, `mission_log`, `mission_control`, `approval_requests`, `circuit_breaker`
- Tabelas memory_service: `episodic_events`, `semantic_facts`, `procedural_patterns`, `graph_nodes`, `graph_edges`

## Certificação de autonomia — CERT-001
- Engenharia da base: em progresso — P2 e P3 com ressalva
- Autonomia Total Real: **NÃO CERTIFICADA** — requer Log Humano válido
- Nível 5 operacional: **NÃO CERTIFICADO** — requer Log Humano válido

## Porta local
- `main_fase2.py`: `127.0.0.1:37777`

## Memory Service — MACROBLOCO C
- **IMPLEMENTADO E APROVADO** — 2026-03-18
- reflection_engine: `consolidate_signals`, `update_pattern_score` (sem usage_count), `run_reflection` (escopado)
- `list_reflection_signals(scope=)` com match exato via substr/length (sem LIKE underscore wildcard)
- `build_agent_context` ranqueia procedural por success_rate DESC + reflection_summary escopado com fallback global
- Endpoints: `POST /memory/reflect/run`, `GET /agents/{id}/build-context`
- Decisão: D-039

## MACROBLOCO D — Watchdog
- **IMPLEMENTADO E APROVADO** — 2026-03-18
- Módulo: `robo_mae/watchdog.py` (WatchdogResult, WatchdogScanner, scan_once, run_loop)
- Endpoint: `POST /watchdog/scan` (auth obrigatória, retorna scanned/resumed/quarantined/failed/noop)
- Integração: lifespan com scan imediato no startup + shutdown limpo
- context_json: persistido em mission_control no /missions/run (idempotente via IS NULL)
- _redispatch_mission: redespacho formal sem bypassar claim/takeover/fencing
- Separação: robo_mae/watchdog.py NÃO importa memory_service
- Testes: T48–T56 (7 unitários + 2 integração)
- Decisão: D-040

## Git
- Branch: `padrão`
- Último commit: `1fd2315`
