# CLAUDE.md — JOD_ROBO

Instruções para Claude Code neste projeto.

## Ao iniciar qualquer conversa

Ler obrigatoriamente (nesta ordem):
1. `/home/wsl/JOD_ROBO/memory/current_state.md` — estado atual do projeto
2. `/home/wsl/JOD_ROBO/memory/constraints.md` — o que não pode ser feito
3. `/home/wsl/JOD_ROBO/memory/user_preferences.md` — como o usuário quer trabalhar
4. `/home/wsl/JOD_ROBO/memory/next_step.md` — próxima etapa oficial

Leitura opcional (quando relevante):
- `/home/wsl/JOD_ROBO/memory/decisions.md` — decisões técnicas tomadas
- `/home/wsl/JOD_ROBO/memory/architecture.md` — arquitetura resumida

**Não tratar o resumo de sessão anterior como verdade sem conferir o arquivo real.**
Resumos podem estar desatualizados ou incompletos.

## Regra de diff obrigatória

Antes de qualquer edição em qualquer arquivo do projeto:
- Mostrar o trecho completo que será alterado (old + new) em texto
- Incluir localização exata (número de linha aproximado)
- Aguardar aprovação explícita antes de executar o Edit tool
- O diálogo do Edit tool não exibe conteúdo na UI do usuário

## decisions.md é append-only

- Nunca sobrescrever uma entrada existente em `decisions.md`
- Toda nova entrada deve incluir data e motivo
- Preservar histórico completo — decisões anteriores nunca são apagadas

## Ao encerrar a conversa (somente se houve mudanças reais)

Atualizar apenas:
- `current_state.md` — refletir o novo estado com precisão
- `next_step.md` — **somente se a etapa atual estiver realmente encerrada com evidência**
- `decisions.md` — adicionar novas decisões em append (nunca sobrescrever)

Não atualizar durante a conversa — apenas ao final, após tudo concluído.
Não marcar etapa como concluída sem checklist validado.

## Arquivos protegidos — nunca editar sem instrução explícita

- `jod_brain_main.py`
- `jod_brain/` (todo o diretório)
- `app/main.py`
- `requirements.txt`
- `Dockerfile`
- `.env`
- `templates/finalizer_manifest.json`

## Constraints de comportamento

- Não improvisar funcionalidades não solicitadas
- Não mudar escopo
- Não criar arquivos fora da lista solicitada
- Mudança mínima e auditável em cada edição
- Ver `memory/constraints.md` para lista completa
- Ver `memory/user_preferences.md` para estilo de trabalho
