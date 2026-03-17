# Arquitetura — JOD_ROBO

**Atualizado em:** 2026-03-15

## Estrutura de diretórios

    JOD_ROBO/
    ├── main_fase2.py              # API principal (FastAPI, porta 37777)
    ├── jod_brain_main.py          # Loop autônomo (CLI + --loop)
    ├── app/
    │   └── main.py                # Fachada REST para jod_brain (Railway)
    ├── jod_brain/                 # Módulos do agente JOD
    │   ├── agents.py              # arquiteto, executor, revisor
    │   ├── io.py                  # write_file, git_commit_push
    │   └── memory.py              # load/save .jod_memory.json
    ├── templates/
    │   ├── finalizer_agent.json   # Template do Agente Finalizador
    │   └── finalizer_manifest.json
    ├── agents/                    # Agentes Python
    ├── scripts/                   # Scripts Python
    ├── tests/
    ├── memory/                    # Memória persistente do projeto
    ├── jod_robo.db                # SQLite
    ├── .jod_memory.json           # Memória do agente JOD
    └── CLAUDE.md

## Camadas da API (main_fase2.py)

    Request
      └── FastAPI route
            └── async helper (_async_*)
                  └── DB helper (sync, _db_*)
                        └── SQLAlchemy Session → jod_robo.db

## Tabelas do banco

| Tabela | Uso |
|---|---|
| `agents` | Registro de todos os agentes |
| `finalizer_manifests` | Manifesto por agent_id (1:1) |
| `finalizer_snapshots` | Snapshot de arquivo antes de write_file |
| `finalizer_audit` | Trilha de auditoria de cada ação do Finalizador |

## Rotas — main_fase2.py

### Agentes base
- `GET /agents`
- `POST /agents`
- `GET /agents/{id}`
- `POST /agents/{id}/clone`
- `POST /agents/{id}/validate`
- `POST /agents/{id}/activate`

### AI / Orchestrate
- `POST /ai/chat`
- `POST /orchestrate`

### Finalizador (Agente 2)
- `POST /agents/finalizer`
- `GET /agents/{id}/finalizer/manifest`
- `POST /agents/{id}/finalizer/validate`
- `POST /agents/{id}/finalizer/activate`
- `POST /agents/{id}/finalizer/execute`
- `POST /agents/{id}/finalizer/rollback/{snap_id}`
- `GET /agents/{id}/finalizer/audit`

### Health / Queue
- `GET /health/live`
- `GET /health/ready`
- `GET /queue/status`

## Constantes críticas (main_fase2.py)

    BASE_DIR = Path("/home/wsl/JOD_ROBO").resolve()

    _FINALIZER_ALWAYS_FORBIDDEN      = {"modify_manifest", "alter_permissions", "install_package"}
    _FINALIZER_ALWAYS_NEEDS_APPROVAL = {"run_script", "git_push", "delete_file", "access_secret", "edit_core"}
    _FINALIZER_IMPLEMENTED           = {"write_file", "read_file", "list_dir"}
