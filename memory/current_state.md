# Estado Atual do Projeto — JOD_ROBO

**Atualizado em:** 2026-03-17

## Arquivos principais

| Arquivo | Papel |
|---|---|
| `main_fase2.py` | Core da API — FastAPI + SQLAlchemy + fila assíncrona |
| `jod_brain_main.py` | Loop autônomo do agente JOD (arquiteto → executor → revisor → git) |
| `app/main.py` | Fachada REST para `jod_brain_main.py` (Railway) |
| `templates/finalizer_agent.json` | Template do Agente Finalizador |
| `templates/finalizer_manifest.json` | Manifesto padrão do Finalizador |
| `templates/guardian_agent.json` | Template do Agente Guardião |
| `tests/test_b1_stale_attestation.py` | Suíte B1 — rastreamento de commit físico de I/O |
| `tests/test_b1_2_guardian_veto_e2e.py` | Suíte B1.2 — veto E2E real do Guardião |

## Status de implementação

### Agente 2 — Finalizador — encerrado em 10/10 (D-016)
### Agente 3 — Guardião — encerrado em 10/10 (D-019)
### B1 — Rastreamento de commit físico de I/O — encerrado em 10/10 (D-022)
### B1.2 — Veto E2E real do Guardião — encerrado em 10/10 (D-024)

Suíte B1.2: `JOD_ENV=test pytest tests/test_b1_2_guardian_veto_e2e.py -v` → `4 passed`.
Regressão: 44/44 passed. Suíte B1: 5/5 passed.

O que foi implantado em B1.2:
- `_apply_guardian_policy` extendida com `target_path: Optional[str] = None`
- Regras path-based: `restricted/` → blocked; `pending/` → needs_approval
- `_guardian_attest` atualizado para propagar `target_path` à política
- Suíte `tests/test_b1_2_guardian_veto_e2e.py` criada com 4 testes

### Rotas implementadas em main_fase2.py

```
POST   /agents/finalizer
GET    /agents/{id}/finalizer/manifest
POST   /agents/{id}/finalizer/validate
POST   /agents/{id}/finalizer/activate
POST   /agents/{id}/finalizer/execute
POST   /agents/{id}/finalizer/rollback/{snap_id}
GET    /agents/{id}/finalizer/audit

POST   /agents/guardian
POST   /agents/{id}/guardian/validate
POST   /agents/{id}/guardian/activate
POST   /agents/{id}/guardian/check
GET    /agents/{id}/guardian/audit

POST   /test/io-fail/set    (JOD_ENV=test only)
POST   /test/io-fail/clear  (JOD_ENV=test only)
```

### Banco de dados
- SQLite em `jod_robo.db`
- Tabelas: `agents`, `finalizer_manifests`, `finalizer_snapshots`, `finalizer_audit`, `guardian_audit`, `integration_audit`
- `integration_audit` colunas B1: `io_committed`, `io_failure_reason`, `io_finalized_at`

### Porta local
- `main_fase2.py`: `127.0.0.1:37777`

## Git
- Branch: `padrão`
- Último commit: `8df18ca`
- `main_fase2.py`, `tests/test_b1_stale_attestation.py`, `tests/test_b1_2_guardian_veto_e2e.py` modificados/criados e não commitados
