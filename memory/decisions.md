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

## D-025 — P1: serialização por target_path
- **Data:** 2026-03-17
- **Decisão:** `asyncio.Lock` keyed por `target_path` via `_get_path_lock()` e `_path_locks_mutex`
- **Motivo:** impedir race condition destrutiva quando dois requests disputam o mesmo arquivo
- **Evidência:** `test_b2_serialization_and_logs.py` — 3 testes de concorrência passed em runtime local
- **Status:** aprovado

## D-026 — P2: logs JSON + correlation_id — com ressalva
- **Data:** 2026-03-17
- **Decisão:** `_JsonFormatter` + `_setup_logging()` + `_CorrelationMiddleware` + `ContextVar`
- **Motivo:** rastreabilidade ponta a ponta — correlation_id propagado em todos os logs e headers
- **Evidência:** 3 testes passed — header X-Correlation-Id presente, echo de cid passando
- **Ressalva:** campo `ts` exibiu `"%f"` literal em vez de microsegundos reais. `formatTime` com `"%Y-%m-%dT%H:%M:%S.%f"` não funciona nativamente — `%f` não é suportado por `logging.Formatter.formatTime`. Requer correção via `datetime.now().strftime` ou `record.created`.
- **Status:** NÃO CERTIFICADO 10/10 — requer correção do ts antes de fechar

## D-041 — P2 certificado: ts com microsegundos reais travado por teste unitário
- **Data:** 2026-03-18
- **Decisão:** implementação `_JsonFormatter` confirmada como correta — usa `datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{int(record.created % 1 * 1e6):06d}"`, nunca `%f` literal
- **Motivo:** ressalva D-026 era de versão anterior; código atual já produz microsegundos reais (ex: `2026-03-18T21:13:08.332157`)
- **Contrato travado:** `test_json_formatter_ts_has_real_microseconds` em `test_b2_serialization_and_logs.py` — valida regex `\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}` e ausência de `%f` literal
- **Evidência:** 1 passed + 145/145 regressão local verde — 2026-03-18
- **Status:** CERTIFICADO 10/10

## D-027 — P3: CI/CD GitHub Actions — com ressalva
- **Data:** 2026-03-17
- **Decisão:** `.github/workflows/ci.yml` criado — push/PR dispara lint + 59 testes + upload de artefatos
- **Motivo:** impedir regressão silenciosa — nenhum merge sem pipeline verde
- **Evidência:** simulação local — 59 passed em 6.75s, `test-results.xml` gerado
- **Ressalva:** sem evidência remota de GitHub Actions executando. Requer push para origin + URL de run verde confirmada.
- **Status:** NÃO CERTIFICADO 10/10 — requer validação remota

## D-042 — P3 certificado: GitHub Actions verde com suíte completa
- **Data:** 2026-03-18
- **Decisão:** workflow corrigido para branch `padrão` + 144 testes (todos os 13 arquivos) + paths dinâmicos em todos os test files e `main_fase2.py`
- **Motivo:** ressalva D-027 — branch não disparava CI; workflow executava apenas 59/144 testes; paths hardcoded quebrariam em `/home/runner/work/...`
- **Correções aplicadas:**
  - `main_fase2.py`: `BASE_DIR = Path(__file__).parent.resolve()` (era hardcoded)
  - 12 arquivos de teste: `DB_PATH`/`BASE_DIR`/`sys.path.insert` convertidos para `Path(__file__).parent.parent` ou `os.path.dirname`
  - `ci.yml`: trigger inclui branch `padrão`; test list expandida de 6 para 13 arquivos (59→145 testes)
- **Evidência remota:** URL do GitHub Actions run — pendente confirmação pós-push
- **Status:** PENDENTE evidência remota (push em andamento)

## D-028 — Robô-mãe só inicia após base limpa
- **Data:** 2026-03-17
- **Decisão:** o Robô-mãe não pode ser iniciado enquanto P2 e P3 tiverem ressalva técnica aberta
- **Motivo:** construir orquestração sobre base com logging quebrado e CI não validado remotamente é dívida técnica estrutural
- **Ordem obrigatória:** corrigir ts → validar P2 → evidência remota P3 → revisão final → Robô-mãe

## D-029 — jod_brain_main.py classificado como human-in-the-loop síncrono
- **Data:** 2026-03-17
- **Decisão:** `jod_brain_main.py` contém `input("Aprovar e executar? [sim/nao]")` — aprovação humana síncrona bloqueante no meio do fluxo de execução
- **Classificação:** human-in-the-loop — Nível 1-2 de maturidade operacional
- **Não é:** autonomia total real, Nível 5, nem equivalente ao Log Humano posterior
- **Distinção obrigatória:**
  - comando inicial humano = permitido em qualquer nível
  - aprovação síncrona no meio do fluxo = humano é parte do executor, não observador
  - Log Humano posterior = auditor externo, não destravamento de execução
- **Motivo:** registrar formalmente para que o Robô-mãe nasça sem este padrão
- **Referência:** CERT-001

## D-030 — Modelo INTERNO escolhido para o Robô-mãe
- **Data:** 2026-03-17
- **Decisão:** o Robô-mãe é um módulo Python dentro do mesmo processo que `main_fase2.py`; lê estado via SQLAlchemy (`Session`) e emite ações via HTTP loopback para os endpoints REST existentes
- **Motivo:** verificação de `io_committed` exige leitura direta de `integration_audit`; criar endpoint REST só para isso aumentaria a superfície sem benefício real; acesso via `SessionLocal` já é auditável
- **Fronteira:** leitura de estado = DB direto; emissão de ações = REST (para manter audit trail)

## D-031 — Tabela real de agentes é `agents` (única)
- **Data:** 2026-03-17
- **Decisão:** tanto finalizer quanto guardian são persistidos em `agents`; distinção por `template_name` (`"finalizer_agent"` ou `"guardian_agent"`); `finalizer_agents` e `guardian_agents` não existem
- **Motivo:** inspeção direta do código confirmou `AgentRecord.__tablename__ = "agents"` como único ORM de agentes
- **Consequência:** `AgentRegistry.get_agent_state()` usa `SELECT id, status, template_name FROM agents WHERE id = :aid`

## D-032 — ensure_active com verificação final autoritativa via DB
- **Data:** 2026-03-17
- **Decisão:** `ensure_active` aceita 200 ou 409 de validate/activate; o gate de sucesso é exclusivamente a re-leitura do `status` em `agents` após as chamadas REST; HTTP response não é suficiente
- **Motivo:** 409 em activate pode indicar "já active" (sucesso) ou "não validated" (falha); só o DB diz qual é o caso real

## D-033 — MVP do Robô-mãe implementado com 5 testes verdes
- **Data:** 2026-03-17
- **Decisão:** MVP do Robô-mãe implementado em `robo_mae/` com endpoint `POST /missions/run`; tabela `mission_log` com migração idempotente; execução sequencial abort-on-first-error
- **Evidências:** 5/5 testes do MVP verdes; 53/53 regressão completa verde; `mission_log` populado com status corretos por tipo (applied, vetoed, error, dry_run_ok)
- **Componentes:** `context.py`, `registry.py`, `executor.py`, `log.py`, `reporter.py`

## D-034 — X-Correlation-Id = mission_id propagado em todos os requests internos
- **Data:** 2026-03-18
- **Decisão:** `run_mission` constrói `hdrs` com `"X-Correlation-Id": req.mission_id`; todos os requests internos do executor (validate, activate, execute) carregam esse header; `_CorrelationMiddleware` propaga para o ContextVar; logs JSON do servidor incluem `"correlation_id": mission_id` durante a execução da missão
- **Evidências:** T6 prova echo do header na resposta outer; T7 prova entradas em uvicorn.log com correlation_id = mission_id a partir de log.info("Agente ativado:") gerado pelo activate interno
- **Resultado:** 7/7 testes do robô-mãe + 53/53 regressão = 60/60 verde

## D-035 — B2: serialização por target_path no MissionExecutor
- **Data:** 2026-03-18
- **Decisão:** `robo_mae/executor.py` mantém registro de `asyncio.Lock` por `target_path` no nível de módulo (`_exec_path_locks`); `_execute_step` delega para `_do_execute` envolvendo o HTTP call em `async with path_lock`; missões concorrentes escrevendo no mesmo path são serializadas antes do request
- **Garantia:** defense-in-depth além do `_get_path_lock` já existente no servidor; fila de espera ocorre no nível do executor, não apenas no servidor
- **Evidência:** T8 — 5 missões concorrentes, mesmo path, todas returned 200+applied, conteúdo sem corrupção, sem shadow órfão; 8/8 robô-mãe + 59/59 regressão = 67/67 verde
- **Padrão correto para teste concurrent:** `async def _run(): return await asyncio.gather(...)` + `asyncio.run(_run())`; shadow search: `basename = Path(target).name` + `BASE_DIR.rglob(f".{basename}.*.jod_tmp")`

## D-040 — MACROBLOCO D: watchdog autônomo com redespacho formal
- **Data:** 2026-03-18
- **Decisão:** `robo_mae/watchdog.py` — WatchdogScanner + WatchdogResult + run_loop. scan_once() varre mission_control WHERE status IN ('RUNNING', 'WAITING_APPROVAL'), delega a reconcile() e age apenas sobre o resultado: QUARANTINE → quarantine(), FAIL → contabiliza, NOOP → contabiliza, RESUME → asyncio.create_task(_redispatch_mission). Redespacho formal via context_json persistido em mission_control na criação da missão. Endpoint POST /watchdog/scan com auth. Lifespan integra startup (scan imediato) + shutdown limpo. SEM import de memory_service. T48–T56: 9 passed. Regressão: 144 passed.
- **Motivo:** watchdog autônomo que detecta missões travadas e as redespacha pelo caminho normal (claim/takeover/fencing), sem bypassar nenhum guardrail do core transacional.

## D-039 — MACROBLOCO C: reflection_engine + build_agent integrado
- **Data:** 2026-03-18
- **Decisão:** `reflection_engine.py` roda fora do caminho crítico; lê de `episodic_events` e `procedural_patterns`; escreve apenas em `semantic_facts` e `procedural_patterns.success_rate/updated_at`; nunca toca `usage_count`, `mission_control`, `mission_log`, `approval_requests` ou `circuit_breaker`
- **Contrato de escopo:** `run_reflection(agent_id=X)` usa apenas eventos de X em `_adjust_patterns`; `agent_id=None` é global; `build_agent_context` prioriza `list_reflection_signals(scope=agent_id)` com fallback para `scope="global"` quando vazio
- **Guardrail SQLite underscore:** `list_reflection_signals(scope=)` usa `substr/length` para match exato de sufixo — nunca `LIKE '%_scope'` porque `_` é wildcard no SQLite. T44 valida que `applied_ag-x` e `applied_xag` não são retornados ao buscar `scope="ag"`
- **usage_count:** soberania do executor — `update_pattern_score()` toca apenas `success_rate` e `updated_at`; T40 assert explícito `usage_count == 0` após reflexão
- **Endpoints:** `POST /memory/reflect/run` (on-demand, advisory_only); `GET /agents/{id}/build-context` (contexto enriquecido advisory_only); `reflect_and_consolidate()` stub permanece intacto (T30 válido)
- **Evidência:** T39–T47 (6 unitários + 3 endpoint) + 135/135 regressão verde; commit 1fd2315

## D-038 — MACROBLOCO B: memory_service separado — episódica, semântica, procedural, graph
- **Data:** 2026-03-18
- **Decisão:** `memory_service/` completamente separado de `robo_mae/` e do core crítico; nenhuma função de memory_service participa de mission execution, ownership, lock_version, heartbeat, retry, recovery, quarantine, fencing ou approval
- **Contrato formal:** `policy_guard.enforce_advisory()` é chamado em toda saída do `RetrievalGateway`; se `advisory_only` não for True, `MemoryGovernanceError` é levantada antes de retornar — memória cognitiva não pode ser usada operacionalmente
- **Guardrail build_agent_context:** graph prioriza `list_graph_neighbors(agent_node_id)` quando existe nó com `label=agent_id`; fallback para `list_graph_nodes(limit=20)` quando sem vínculo específico — contrato fechado via `find_node_by_label()`
- **Tabelas:** `episodic_events`, `semantic_facts` (UNIQUE category+key), `procedural_patterns` (UNIQUE name), `graph_nodes`, `graph_edges` (UNIQUE source+relation+target)
- **Endpoints:** 11 rotas `/memory/` em `main_fase2.py`; schemas `Mem*` adicionados ao bloco Pydantic existente
- **reflect_and_consolidate():** stub — registra intenção como `consolidation_intent` episódico; retorna `pending_consolidation`; consolidação real fora do escopo
- **Evidência:** T23–T38 (11 unitários + 5 endpoint) + 126/126 regressão verde; commit e1937a2

## D-036 — Fase 1: Recuperação real pós-queda — encerrada 10/10
- **Data:** 2026-03-18
- **Decisão:** implementação completa de mission_control, ownership/claim/takeover, heartbeat, fencing hard, two-phase step logging e reconciliador com matriz exaustiva
- **Arquivos novos:** `robo_mae/mission_control.py` (MissionControl, FencingError, ReconcileDecision, run_heartbeat), `tests/test_recovery.py` (T9–T16)
- **Arquivos alterados:** `robo_mae/executor.py` (fluxo A–E com reconcile como autoridade), `robo_mae/log.py` (begin_step + finish_step), `main_fase2.py` (_migrate_mission_control)
- **Semântica exata:** `claim()` PENDING→RUNNING; `takeover()` RUNNING+stale→RUNNING (novo dono); zero sobreposição
- **QUARANTINE:** estado formal explícito no mission_control, nunca erro genérico silencioso
- **reconcile():** autoridade única de resume_from_step; executor consome sem recalcular
- **Two-phase logging:** `begin_step` INSERT RUNNING → `finish_step` UPDATE resultado final
- **Repair:** executor repara entrada RUNNING do passo anterior (io_committed=1 confirmado) antes de executar
- **Evidência:** T9–T14 unitários 6/6 + T15 recovery real (não-duplicação provada) + T16 fencing real (HTTP 500 + DB intacto); T1–T8 regressão intacta; 104/104 verde
