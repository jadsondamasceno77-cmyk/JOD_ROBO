# Estado Atual do Projeto — JOD_ROBO
**Atualizado em:** 2026-03-17

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
- 59 passed, 0 failed — última execução: 2026-03-17

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
- **NÃO INICIADO**
- só inicia após P2 e P3 certificados limpos + revisão geral final da base

## Certificação de autonomia — CERT-001
- Engenharia da base: em progresso — P2 e P3 com ressalva
- Autonomia Total Real: **NÃO CERTIFICADA** — requer Log Humano válido
- Nível 5 operacional: **NÃO CERTIFICADO** — requer Log Humano válido

## Banco de dados
- SQLite em `jod_robo.db`
- Tabelas: `agents`, `finalizer_manifests`, `finalizer_snapshots`, `finalizer_audit`, `guardian_audit`, `integration_audit`
- `integration_audit` colunas B1: `io_committed`, `io_failure_reason`, `io_finalized_at`

## Porta local
- `main_fase2.py`: `127.0.0.1:37777`

## Git
- Branch: `padrão`
- Último commit: `f34d839`
