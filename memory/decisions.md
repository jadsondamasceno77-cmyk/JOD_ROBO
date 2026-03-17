# Decisões Técnicas — JOD_ROBO

Formato: **append-only**. Nunca sobrescrever uma entrada existente.
Toda nova entrada deve incluir data e motivo.

---

## D-001 — Pydantic v2 com ConfigDict
- **Data:** 2026-03-15
- **Decisão:** todos os modelos usam `model_config = ConfigDict(extra="forbid")`
- **Motivo:** validação estrita, sem campos inesperados em runtime

## D-002 — SQLAlchemy + SQLite local
- **Data:** 2026-03-15
- **Decisão:** persistência via SQLAlchemy ORM com SQLite em `jod_robo.db`
- **Motivo:** simplicidade, sem dependência externa para o ambiente WSL

## D-003 — Separação builder / persister na auditoria
- **Data:** 2026-03-15
- **Decisão:** `_build_audit(...)` constrói `FinalizerAuditRecord` em memória; `_db_save_audit(rec)` persiste. Padrão obrigatório: `_db_save_audit(_build_audit(...))`
- **Motivo:** explicitação do contrato de persistência — auditoria não pode ser silenciosa

## D-004 — Reuso de `_async_activate_agent`
- **Data:** 2026-03-15
- **Decisão:** `_async_activate_finalizer` delega para `_async_activate_agent` (sem duplicar lógica 404/409/save)
- **Motivo:** DRY — lógica de ativação já está encapsulada no helper base

## D-005 — Anti-path-traversal via Path.resolve()
- **Data:** 2026-03-15
- **Decisão:** `_check_path_allowed` rejeita paths absolutos, componentes `..`, e canonicaliza com `(BASE_DIR / p).resolve()` + `relative_to(BASE_DIR)`
- **Motivo:** impede escape de BASE_DIR por qualquer variante de traversal

## D-006 — 6 regras de política com precedência hardcoded
- **Data:** 2026-03-15
- **Decisão:** ordem obrigatória e imutável:
  1. `_FINALIZER_ALWAYS_FORBIDDEN` → forbidden
  2. `_FINALIZER_ALWAYS_NEEDS_APPROVAL` → needs_approval
  3. `manifest.requires_approval` → needs_approval
  4. `action not in manifest.allowed_actions` → forbidden
  5. Validação de path → forbidden se unsafe
  6. `action not in _FINALIZER_IMPLEMENTED` → HTTP 501
- **Motivo:** hardcoded garante que manifesto não pode escalar privilégios

## D-007 — Ciclo de vida obrigatório: draft → validated → active
- **Data:** 2026-03-15
- **Decisão:** agente Finalizador só executa com status `active`; ativação requer `validated`; validação requer `draft` + manifesto presente
- **Motivo:** nenhum agente opera sem passar por validação explícita

## D-008 — Diff completo obrigatório antes de cada Edit
- **Data:** 2026-03-15
- **Decisão:** nenhuma edição em `main_fase2.py` sem mostrar o trecho exato (old + new) em texto antes do tool call
- **Motivo:** o diálogo do Edit tool não exibe conteúdo completo na UI do usuário

## D-009 — Ordem de fases do projeto
- **Data:** 2026-03-15
- **Decisão:** a ordem obrigatória de avanço é **Finalizador → Guardião → Integração**
- **Motivo:** cada camada depende da anterior; não avançar sem a fase corrente validada ponta a ponta
- **Regra-mãe:** nada sai sem evidência validada — sintaxe OK não equivale a conclusão de fase

## D-010 — Finalizador não é concluído sem teste ponta a ponta
- **Data:** 2026-03-15
- **Decisão:** a Fase A do Finalizador só pode ser marcada como concluída após validação em runtime de todas as rotas
- **Motivo:** evitar falsa sensação de progresso; código no arquivo ≠ funcionalidade validada

## D-011 — Agente 2 — Finalizador validado ponta a ponta em runtime
- **Data:** 2026-03-15
- **Decisão:** o Agente 2 — Finalizador está validado em runtime. Todos os 14 itens do checklist confirmados.
- **Motivo:** evidência real coletada via testes das rotas — não apenas sintaxe ou startup

## D-012 — Desalinhamento semântico de status no Finalizador
- **Data:** 2026-03-15
- **Decisão:** registrar como débito técnico que `_async_finalizer_execute` retorna `status: "ok"` em vez de `"applied"` (mode=apply) ou `"dry_run_ok"` (mode=dry_run)
- **Motivo:** o contrato semântico está inconsistente; deve ser corrigido antes de qualquer integração downstream que dependa do campo `status`
- **Ação futura:** corrigir apenas quando explicitamente solicitado; não corrigir autonomamente

## D-013 — Contrato semântico de status do Finalizador fechado
- **Data:** 2026-03-15
- **Decisão:** `_async_finalizer_execute` agora retorna `status: "planned"` (mode=plan), `"dry_run_ok"` (mode=dry_run) e `"applied"` (mode=apply). O `status: "ok"` genérico foi removido.
- **Motivo:** fecha o débito técnico registrado em D-012; contrato semântico consistente antes de qualquer integração downstream

## D-014 — Autenticação nas rotas sensíveis do Finalizador
- **Data:** 2026-03-15
- **Decisão:** 6 rotas POST/GET do Finalizador exigem `Authorization: Bearer {token}` via `verify_token`. GET `/finalizer/manifest` permanece público, alinhado com o padrão de GET `/agents`.
- **Motivo:** rotas de mutação de estado (criar, validar, ativar, executar, rollback, audit) não devem ser acessíveis sem autenticação

## D-015 — Suíte automatizada do Finalizador validada: 16/16
- **Data:** 2026-03-15
- **Decisão:** `python3 -m pytest tests/test_finalizer.py -v` → 16 passed. Cobre checklist completo: ciclo de vida, políticas, modos de execução, snapshot, rollback, trilha de auditoria e auth.
- **Motivo:** evidência automatizada complementa a validação manual anterior (D-011); bloco do Finalizador encerrado em 10/10

## D-016 — Agente 2 — Finalizador encerrado em 10/10
- **Data:** 2026-03-15
- **Decisão:** o bloco do Finalizador está definitivamente encerrado. Não reabrir sem bug confirmado e instrução explícita do usuário.
- **Motivo:** todas as dimensões validadas: implementação, runtime, contrato semântico, autenticação e suíte automatizada; response models explícitos confirmados nas rotas de manifest e execute

## D-017 — Guardião sem manifesto na v1
- **Data:** 2026-03-16
- **Decisão:** o Agente Guardião não usa manifesto. `CreateGuardianAgentRequest` contém apenas `name: str`. O ciclo de vida é `draft → validated → active` sem verificação de manifesto na ativação.
- **Motivo:** o Guardião não executa ações no sistema de arquivos — apenas avalia e veredita. Manifesto seria overhead sem função na v1. Pode ser adicionado em versão futura se o escopo do Guardião expandir.

## D-018 — Política do Guardião ancorada nos action strings do Finalizador
- **Data:** 2026-03-16
- **Decisão:** `_GUARDIAN_ALWAYS_BLOCKED` = `{"modify_manifest", "alter_permissions", "install_package"}` (espelho de `_FINALIZER_ALWAYS_FORBIDDEN`). `_GUARDIAN_ALWAYS_NEEDS_APPROVAL` = `{"run_script", "git_push", "delete_file", "access_secret", "edit_core"}` (espelho de `_FINALIZER_ALWAYS_NEEDS_APPROVAL`). Qualquer ação fora desses sets retorna `approved`.
- **Motivo:** única base não especulativa disponível na v1 — os action strings já existiam e eram testados no Finalizador. Extensão da política do Guardião deve ser registrada em `decisions.md` antes de implementação.

## D-019 — Agente 3 — Guardião encerrado em 10/10
- **Data:** 2026-03-16
- **Decisão:** o bloco do Guardião está definitivamente encerrado. Não reabrir sem bug confirmado e instrução explícita do usuário.
- **Motivo:** todas as dimensões validadas: `ast.parse` OK, startup OK, 13 itens de checklist runtime confirmados, `pytest tests/test_guardian.py -v` → 15 passed. Padrão de implementação alinhado com o Finalizador.

## D-020 — Trava de excelência obrigatória antes do fechamento de fase
- **Data:** 2026-03-16
- **Decisão:** uma fase só pode ser considerada concluída após duas etapas distintas: (1) validação técnica real — sintaxe, startup, checklist runtime, pytest verde; (2) revisão final de excelência — verificação de que o que foi entregue está no padrão final desejado do projeto, não apenas funcional.
- **Motivo:** fases entregues apenas como "funciona agora" geram retrabalho posterior. O padrão do projeto é fazer já no nível final — não aprovar fase que exigirá revisão de qualidade futura. Regra válida daqui para frente para toda fase aberta ou futura do projeto.

## D-021 — B1: rastreamento de commit físico de I/O em integration_audit
- **Data:** 2026-03-17
- **Decisão:** três colunas adicionadas a `integration_audit` via migração idempotente (`_migrate_integration_audit`): `io_committed` (INTEGER, default 0), `io_failure_reason` (TEXT), `io_finalized_at` (TEXT). Helpers `_db_mark_io_committed` e `_db_mark_io_failed` atualizam o registro após `os.replace()`. Hook de teste via `app.state.io_fail_target` ativo apenas com `JOD_ENV=test`.
- **Motivo:** o sistema precisava de trilha honesta diferenciando "guardian aprovou" de "arquivo realmente escrito no disco". Falha de I/O após fsync mas antes de os.replace() agora é capturada, o shadow é limpo e o motivo é registrado — sem silêncio.

## D-022 — B1 encerrado em 10/10
- **Data:** 2026-03-17
- **Decisão:** o bloco B1 está definitivamente encerrado. Suíte B1: 5/5 passed. Regressão: 44/44 passed. Não reabrir sem bug confirmado e instrução explícita.
- **Motivo:** todas as dimensões validadas: schema (3 colunas novas), sucesso (io_committed=1), falha (io_committed=0 + reason preenchido), cross-trail íntegro, dry_run sem aumentar commit, sem shadow órfão, sem guardian completa corretamente.

## D-023 — B1.2: veto E2E real do Guardião por path-based policy
- **Data:** 2026-03-17
- **Decisão:** `_apply_guardian_policy` extendida com `target_path: Optional[str] = None`. Regras adicionadas: `write_file` + `target_path.startswith("restricted/")` → `blocked`; `write_file` + `target_path.startswith("pending/")` → `needs_approval`. `_guardian_attest` atualizado para propagar `target_path`. Suíte B1.2: 4/4 passed. Regressão completa: 44/44 passed.
- **Motivo:** o sistema precisava demonstrar que o Guardião veta a ação ANTES de qualquer I/O — `io_committed=0`, `io_finalized_at=None`, arquivo ausente, shadow ausente, trilha cruzada íntegra com mesmo transaction_id em response/integration_audit/guardian_audit/finalizer_audit.

## D-024 — B1.2 encerrado em 10/10
- **Data:** 2026-03-17
- **Decisão:** o bloco B1.2 está definitivamente encerrado. Não reabrir sem bug confirmado e instrução explícita.
- **Motivo:** blocked → 403, needs_approval → 403, approved → 200 + io_committed=1; cross-trail consistente; sem shadow órfão; regressão 44/44 intacta.
