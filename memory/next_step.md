# Próxima Etapa Oficial — JOD_ROBO
**Atualizado em:** 2026-03-17

## Fases encerradas com evidência real
- Finalizador — 10/10, runtime validado (D-016)
- Guardião — 10/10, runtime validado (D-019)
- B1 stale attestation — 10/10, runtime validado (D-022)
- B1.2 veto E2E real — 10/10, runtime validado (D-024)
- P1 serialização por target_path — aprovado, runtime validado (D-025)

## Fases com ressalva — ainda não certificadas 10/10
- P2 logs JSON + correlation_id — ressalva: ts com "%f" literal (D-026)
- P3 CI/CD — ressalva: sem evidência remota do GitHub Actions (D-027)

## Fase 1 encerrada: Recuperação real pós-queda — 10/10 (D-036)

## Próxima etapa: Fase 2 do core transacional rumo ao Nível 5

### Fases concluídas nesta sessão
- ✅ MVP do Robô-mãe — 5/5 passed, regressão 58/58 verde (D-033)

### Fases concluídas nesta sessão
- ✅ Infraestrutura OpenClaw: Restauração de `TROUBLESHOOTING.md` e `fix_openclaw.sh`
- ✅ LLM Fallback: Timeout do Ollama aumentado para 300s em `jod_brain/llm/__init__.py`

### Próximas etapas recomendadas (sem ordem obrigatória definida pelo usuário)
1. Endurecimento pós-MVP: serialização por target_path no executor
2. Reconciliação automática pós-os.replace (crash recovery de missão)
3. Corrigir campo `ts` do `_JsonFormatter` — microsegundos reais (P2 ressalva)
4. Validar P3 com evidência remota — push + GitHub Actions verde
5. Canal de aprovação humana para needs_approval (human-on-the-loop real)

## Regras obrigatórias do Robô-mãe (para referência futura)
- zero `input()` no meio do fluxo
- humano dispara → sistema executa → humano audita (Log Humano)
- Guardião decide autonomamente — sem aprovação síncrona humana
- classificação: human-on-the-loop, não human-in-the-loop
- referência: D-028, D-029, CERT-001

## CERT-001
- Autonomia Total Real: só certificável após Log Humano válido
- Nível 5 operacional: só certificável após Log Humano válido
