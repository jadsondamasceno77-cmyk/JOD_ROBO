# Constraints do Projeto — JOD_ROBO

**Atualizado em:** 2026-03-15

## Constraints de código

### C-001 — Não mexer no Guardião
- `jod_brain_main.py`, `jod_brain/` e `app/main.py` são protegidos
- Nunca editar sem instrução explícita do usuário

### C-002 — Não mexer no manifesto do Finalizador
- `templates/finalizer_manifest.json` está em `forbidden_paths` do próprio manifesto
- O Finalizador não pode alterar seu próprio manifesto

### C-003 — Não editar fora da allowlist do Finalizador
- `allowed_paths`: `agents/`, `scripts/`, `templates/`, `tests/`
- `forbidden_paths`: `app/`, `jod_brain/`, `.env`, `main_fase2.py`, `jod_brain_main.py`, `requirements.txt`, `Dockerfile`, `templates/finalizer_manifest.json`

### C-004 — Não alterar permissões sem aprovação
- `alter_permissions` está em `_FINALIZER_ALWAYS_FORBIDDEN`

### C-005 — Não instalar pacotes autonomamente
- `install_package` está em `_FINALIZER_ALWAYS_FORBIDDEN`

### C-006 — Não acessar secrets sem aprovação
- `access_secret` está em `_FINALIZER_ALWAYS_NEEDS_APPROVAL`

### C-007 — Não fazer git push sem aprovação
- `git_push` está em `_FINALIZER_ALWAYS_NEEDS_APPROVAL`

## Constraints de processo (para Claude Code)

### P-001 — Diff completo obrigatório antes de cada Edit
- Ver `user_preferences.md` UP-001

### P-002 — Mudança mínima e auditável
- Não refatorar além do solicitado

### P-003 — Não improvisar
- Verificar com Read antes de propor qualquer edição

### P-004 — Aprovação por diff individual
- Cada diff distinto pode exigir aprovação separada

## Constraints de ambiente

### E-001 — WSL2 + Linux
- OS: Linux 6.6.87.2-microsoft-standard-WSL2

### E-002 — Banco local SQLite
- Arquivo: `jod_robo.db`

### E-003 — Porta local 37777
- `main_fase2.py` sobe em `127.0.0.1:37777`
