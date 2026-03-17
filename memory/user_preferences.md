# Preferências do Usuário — JOD_ROBO

**Atualizado em:** 2026-03-15

## UP-001 — Evidência antes de aprovação
- Nunca pedir aprovação de edição sem mostrar o diff completo em texto
- Mostrar: (1) trecho exato alterado, (2) linha antiga, (3) linha nova, (4) qual diff corresponde
- O diálogo do Edit tool não exibe conteúdo na UI — o texto antes do tool call é a evidência real

## UP-002 — Mudança mínima
- Corrigir apenas o que foi explicitamente solicitado
- Não refatorar código vizinho
- Não adicionar comentários, docstrings ou type hints em código não modificado

## UP-003 — Sem improvisação
- Não inventar código que não existe no arquivo real
- Não criar features não solicitadas
- Não mudar escopo sem instrução

## UP-004 — Respostas diretas e concisas
- Não resumir o que acabou de ser feito após cada edição
- Não usar emojis salvo instrução explícita
- Uma frase se resolve em uma frase

## UP-005 — Confirmação de desvios confirmados
- Quando o usuário lista problemas numerados, resolver cada um explicitamente
- Não marcar como resolvido sem mostrar o diff correspondente

## UP-006 — Não alterar arquivos fora do escopo definido
- Confirmar escopo antes de editar mais de um arquivo

## UP-007 — Regra-mãe de aprovação
- Faça exatamente o que foi solicitado
- Não mude o escopo
- Não improvise
- Não invente nada que não exista no arquivo real
- Não peça aprovação sem mostrar o diff completo
- Qualquer desvio será negado

## UP-008 — Padrão de nomes exatos
- Usar exatamente os nomes de arquivo, função e variável que existem no código real
- Não renomear, não abreviar, não criar aliases sem instrução

## UP-009 — Sempre incluir motivo do sim/não
- Quando aprovar ou recusar algo, registrar o motivo para que possa ser citado em contexto futuro
- Claude Code deve sempre incluir o motivo técnico de cada decisão proposta

## UP-010 — Um comando único por fase
- Cada fase tem um único objetivo; não iniciar a próxima antes da atual estar validada
- Não presumir que "implementado" = "concluído"
- Concluído = implementado + testado ponta a ponta + aprovado pelo usuário

## UP-011 — Não reabrir contexto fechado
- Uma decisão aprovada e implementada não deve ser reaberta sem instrução explícita do usuário
- Não propor refatoração de código já aprovado a menos que haja bug confirmado
