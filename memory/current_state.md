# Estado Atual do Projeto — JOD_ROBO
**Atualizado em:** 2026-03-18

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

## Regressão ampliada confirmada localmente
- 104 passed, 0 failed — última execução: 2026-03-18

## Estado de P2 e P3 — com ressalva

### P2 — Logs JSON + correlation_id
- header X-Correlation-Id: passou
- correlation_id propagado: passou
- logs em JSON: passou
- **RESSALVA:** campo `ts` apareceu com `"%f"` literal em vez de microsegundos reais
- **Status: NÃO CERTIFICADO 10/10** — requer correção do timestamp antes de fechar

### P3 — CI/CD GitHub Actions
- workflow `.github/workflows/ci.yml` criado
- simulação local: 59 passed em 6.75s
- **RESSALVA:** sem evidência remota de GitHub Actions executando no repositório
- **Status: NÃO CERTIFICADO 10/10** — requer push + execução remota confirmada

## Robô-mãe
- **MVP IMPLEMENTADO E APROVADO** — 2026-03-17
- Módulo: `robo_mae/` (context, registry, executor, log, reporter)
- Endpoint: `POST /missions/run`
- Tabela nova: `mission_log`
- Suíte: `tests/test_robo_mae.py` — 8/8 passed
- Regressão total: 104/104 passed
- Modelo: INTERNO (DB direto para estado, REST loopback para ações)
- Decisões: D-030, D-031, D-032, D-033, D-034, D-035

## Fase 1 — Recuperação real pós-queda (FECHADA — 2026-03-18)
- **Status: 10/10 fechado (D-036)**
- Novos arquivos: `robo_mae/mission_control.py`, `tests/test_recovery.py`
- Arquivos alterados: `robo_mae/executor.py`, `robo_mae/log.py`, `main_fase2.py`
- Nova tabela: `mission_control` (status, owner_id, lock_version, heartbeat_at, claimed_at, current_step)
- Evolução: `mission_log` + coluna `step_index`
- Testes: T9–T16 — 8/8 passed (6 unitários + T15 recovery real + T16 fencing real)
- Suíte total: 104/104 verde

## Certificação de autonomia — CERT-001
- Engenharia da base: em progresso — P2 e P3 com ressalva
- Autonomia Total Real: **NÃO CERTIFICADA** — requer Log Humano válido
- Nível 5 operacional: **NÃO CERTIFICADO** — requer Log Humano válido

## Banco de dados
- SQLite em `jod_robo.db`
- Tabelas: `agents`, `finalizer_manifests`, `finalizer_snapshots`, `finalizer_audit`, `guardian_audit`, `integration_audit`, `mission_log`
- `integration_audit` colunas B1: `io_committed`, `io_failure_reason`, `io_finalized_at`
- `mission_log`: `id`, `mission_id`, `correlation_id`, `finalizer_id`, `guardian_id`, `action`, `target_path`, `status`, `io_committed`, `transaction_id`, `details`, `created_at`, `step_index`
- `mission_control`: `mission_id`, `status`, `owner_id`, `lock_version`, `heartbeat_at`, `claimed_at`, `current_step`, `created_at`

## Porta local
- `main_fase2.py`: `127.0.0.1:37777`

## Git
- Branch: `padrão`
- Último commit: `f34d839`
