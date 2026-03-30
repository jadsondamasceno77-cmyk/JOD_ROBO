#!/usr/bin/env python3
"""
ELI — 5 Fases completas do Robô Mãe
Cada fase tem tools especializadas que o Agent OS pode invocar.
"""
import os
import json
import asyncio
import httpx
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from typing import Optional

_ELI   = "http://localhost:37779"
_TOKEN = os.getenv("JOD_TRUST_MANIFEST", "jod_robo_trust_2026_secure")

_LLM: Optional[ChatGroq] = None
def _llm() -> ChatGroq:
    global _LLM
    if _LLM is None:
        _LLM = ChatGroq(model="llama-3.3-70b-versatile",
                        api_key=os.getenv("GROQ_API_KEY",""), temperature=0.7)
    return _LLM

def _invoke(prompt: str) -> str:
    r = _llm().invoke(prompt)
    return r.content if hasattr(r, "content") else str(r)

# ══════════════════════════════════════════════════════════════════════════════
# FASE 1 — GESTÃO E DISPONIBILIDADE (Operação 24/7)
# ══════════════════════════════════════════════════════════════════════════════

@tool
async def atendimento_24h(mensagem: str, marca: str, tom: str = "profissional e acolhedor") -> str:
    """
    FASE 1 — Gerente Digital 24/7.
    Responde clientes como braço direito da marca, a qualquer hora.
    mensagem: o que o cliente perguntou/disse.
    marca: nome da empresa/marca.
    tom: tom de voz da marca.
    """
    return await asyncio.get_event_loop().run_in_executor(None, _invoke,
        f"""Você é o gerente digital da marca '{marca}'. Tom: {tom}.
Responda o cliente de forma completa, empática e orientada à venda.
Nunca deixe o cliente sem resposta. Sempre ofereça um próximo passo.

MENSAGEM DO CLIENTE: {mensagem}

Responda como gerente da marca, não como IA."""
    )

@tool
async def agenda_pessoal(acao: str, detalhes: str, marca: str) -> str:
    """
    FASE 1 — Assessor pessoal: organiza agenda, compromissos e tarefas prioritárias.
    acao: 'criar' | 'listar' | 'priorizar' | 'lembrete'.
    detalhes: descrição do compromisso ou período.
    """
    return await asyncio.get_event_loop().run_in_executor(None, _invoke,
        f"""Você é o assessor pessoal da marca '{marca}'.
Ação solicitada: {acao}
Detalhes: {detalhes}

Execute a ação de agenda de forma clara, organizada e prática.
Formate como uma agenda executiva profissional."""
    )

@tool
async def posicionamento_nicho(nicho: str, publico: str, pais: str = "BR") -> str:
    """
    FASE 1 — Análise de posicionamento de mercado.
    Define nicho, diferenciação, concorrentes e oportunidades de posicionamento.
    """
    return await asyncio.get_event_loop().run_in_executor(None, _invoke,
        f"""Você é um estrategista de mercado sênior.
Analise o posicionamento para:
NICHO: {nicho}
PÚBLICO: {publico}
PAÍS/MERCADO: {pais}

Entregue:
1. Análise do mercado (tamanho, oportunidade)
2. Top 3 concorrentes e seus pontos fracos
3. Diferenciação única (o que nos torna imbatíveis)
4. Posicionamento recomendado (frase de 1 linha)
5. Público ideal detalhado (dores, desejos, objeções)"""
    )

# ══════════════════════════════════════════════════════════════════════════════
# FASE 2 — INTELIGÊNCIA E ESTRATÉGIA DE ESCALA
# ══════════════════════════════════════════════════════════════════════════════

@tool
async def reuniao_equipe_conteudo(marca: str, nicho: str, periodo: str = "30 dias") -> str:
    """
    FASE 2 — Planejamento de conteúdo (reunião de toda equipe).
    Gera calendário editorial estratégico com temas, formatos e plataformas.
    """
    return await asyncio.get_event_loop().run_in_executor(None, _invoke,
        f"""Você é o diretor de conteúdo liderando a reunião editorial da marca '{marca}'.
NICHO: {nicho} | PERÍODO: {periodo}

Entregue o planejamento completo:
1. PILARES DE CONTEÚDO (5 temas recorrentes)
2. CALENDÁRIO EDITORIAL — {periodo}:
   - Dia | Plataforma | Formato | Tema | Objetivo
3. MIX DE FORMATOS (% reels, posts, stories, lives, carrosséis)
4. TEMAS SAZONAIS e datas comemorativas do período
5. KPIs a monitorar por semana"""
    )

@tool
async def roteiro_conteudo(tema: str, formato: str, duracao: str, marca: str, publico: str) -> str:
    """
    FASE 2 — Roteiro detalhado de conteúdo pronto para gravar.
    formato: 'reels' | 'video_longo' | 'live' | 'stories' | 'podcast'.
    duracao: ex '30s', '5min', '1h'.
    """
    return await asyncio.get_event_loop().run_in_executor(None, _invoke,
        f"""Você é roteirista profissional de conteúdo digital.
MARCA: {marca} | PÚBLICO: {publico}
TEMA: {tema} | FORMATO: {formato} | DURAÇÃO: {duracao}

ROTEIRO COMPLETO:
⏱️ GANCHO [0-3s]: (frase que para o scroll)
🎬 ABERTURA [3-10s]: (apresentação do problema/promessa)
📖 DESENVOLVIMENTO [{duracao} dividido em blocos]:
   Bloco 1 — (conteúdo principal)
   Bloco 2 — (aprofundamento / virada)
   Bloco 3 — (solução / prova)
🎯 FECHAMENTO: (CTA + call to action)
📝 LEGENDA: (otimizada para plataforma)
#️⃣ HASHTAGS: (mix estratégico)"""
    )

@tool
async def storytelling_personal_branding(nome: str, historia: str, nicho: str) -> str:
    """
    FASE 2 — Storytelling de Personal Branding.
    Transforma a história pessoal em narrativa de autoridade que gera conexão e venda.
    """
    return await asyncio.get_event_loop().run_in_executor(None, _invoke,
        f"""Você é um especialista em Personal Branding e Storytelling.
PESSOA: {nome} | NICHO: {nicho}
HISTÓRIA BRUTA: {historia}

Crie o storytelling de autoridade completo:
1. HISTÓRIA DE ORIGEM (a jornada do herói — dor → transformação)
2. MOMENTO DE VIRADA (o ponto que mudou tudo)
3. MISSÃO DE MARCA (por que você faz isso além do dinheiro)
4. PROVA DE AUTORIDADE (resultados, conquistas, credenciais)
5. HISTÓRIA PARA BIO (versão de 3 linhas para redes sociais)
6. PITCH DE 60 SEGUNDOS (para vídeo de apresentação)
7. FRASE ASSINATURA (que define quem você é)"""
    )

@tool
async def copywriting_produto(produto: str, preco: str, publico: str, objecoes: str) -> str:
    """
    FASE 2 — Copywriting de produto/serviço orientado à conversão.
    Gera copy para anúncio, página de vendas e WhatsApp.
    """
    return await asyncio.get_event_loop().run_in_executor(None, _invoke,
        f"""Você é um copywriter de resposta direta especialista em conversão.
PRODUTO/SERVIÇO: {produto}
PREÇO: {preco}
PÚBLICO: {publico}
OBJEÇÕES COMUNS: {objecoes}

Entregue o pack de copy completo:
1. HEADLINE PRINCIPAL (a promessa irresistível)
2. SUBHEADLINE (reforça e qualifica)
3. COPY PARA ANÚNCIO (150 palavras — problema, agitação, solução)
4. COPY PARA WHATSAPP (mensagem de abordagem quente)
5. COPY PARA STORIES (sequência de 3 slides)
6. QUEBRA DE OBJEÇÕES (resposta a cada objeção listada)
7. GARANTIA (como apresentar para eliminar risco)
8. CTA PRINCIPAL + CTA URGÊNCIA"""
    )

@tool
async def growth_estrategias(marca: str, objetivo: str, orcamento: str, prazo: str) -> str:
    """
    FASE 2 — Estratégias de Growth e alavancagem de escala.
    objetivo: ex 'dobrar seguidores', '100 vendas/mês', '10k leads'.
    orcamento: ex 'R$500/mês', 'orgânico apenas'.
    prazo: ex '30 dias', '90 dias'.
    """
    return await asyncio.get_event_loop().run_in_executor(None, _invoke,
        f"""Você é um Growth Hacker com foco em resultados rápidos e sustentáveis.
MARCA: {marca} | OBJETIVO: {objetivo}
ORÇAMENTO: {orcamento} | PRAZO: {prazo}

PLANO DE GROWTH COMPLETO:
1. DIAGNÓSTICO (onde estamos e onde queremos chegar)
2. QUICK WINS (o que fazer nos primeiros 7 dias para tração rápida)
3. ESTRATÉGIAS ORGÂNICAS (crescimento sem pagar)
4. ESTRATÉGIAS PAGAS (se orçamento > 0)
5. FUNIL DE AQUISIÇÃO (onde captar → qualificar → converter)
6. ALAVANCAS DE ESCALA (parcerias, virais, automações)
7. MÉTRICAS SEMANAIS (o que medir e quando pivotar)
8. PLANO DE 30/60/90 DIAS"""
    )

# ══════════════════════════════════════════════════════════════════════════════
# FASE 3 — CONSTRUÇÃO DE ATIVOS E AUTORIDADE
# ══════════════════════════════════════════════════════════════════════════════

@tool
async def gerar_identidade_visual(marca: str, nicho: str, personalidade: str) -> str:
    """
    FASE 3 — Design gráfico: cria manual de identidade visual completo.
    Entrega: paleta de cores, fontes, estilo visual, diretrizes de uso.
    """
    return await asyncio.get_event_loop().run_in_executor(None, _invoke,
        f"""Você é um diretor de arte e designer de marca sênior.
MARCA: {marca} | NICHO: {nicho} | PERSONALIDADE: {personalidade}

MANUAL DE IDENTIDADE VISUAL:
1. CONCEITO VISUAL (inspiração, referências, mood)
2. PALETA DE CORES:
   - Cor primária: #HEX (nome + significado psicológico)
   - Cor secundária: #HEX
   - Cor de acento: #HEX
   - Neutros: #HEX
3. TIPOGRAFIA:
   - Fonte principal (título): [nome] — por quê?
   - Fonte secundária (corpo): [nome]
   - Fonte de destaque: [nome]
4. ESTILO FOTOGRÁFICO (o que deve e não deve aparecer)
5. ELEMENTOS GRÁFICOS (formas, texturas, ícones característicos)
6. GRID PARA FEED (padrão visual do Instagram)
7. TOM VISUAL EM 3 PALAVRAS"""
    )

@tool
async def gerar_landing_page(produto: str, publico: str, cta: str, beneficios: str) -> str:
    """
    FASE 3 — Gera HTML completo de landing page de alta conversão.
    Retorna código HTML/CSS pronto para publicar.
    """
    loop = asyncio.get_event_loop()
    estrutura = await loop.run_in_executor(None, _invoke,
        f"""Você é um web designer especialista em landing pages de alta conversão.
PRODUTO: {produto} | PÚBLICO: {publico} | CTA: {cta}
BENEFÍCIOS: {beneficios}

Crie o HTML completo de uma landing page com:
- Hero section (headline + subheadline + CTA acima da dobra)
- Seção de dor/problema
- Solução + benefícios (3 cards)
- Prova social (depoimentos placeholder)
- Oferta + preço + garantia
- FAQ (3 perguntas principais)
- CTA final com urgência

Use CSS inline, design moderno, cores baseadas no produto.
Retorne APENAS o HTML completo, sem explicações."""
    )

    # Salva o HTML gerado
    import hashlib, os
    h = hashlib.md5(produto.encode()).hexdigest()[:8]
    path = f"/home/jod_robo/JOD_ROBO/social_sessions/pages/lp_{h}.html"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(estrutura)
    return json.dumps({"status": "gerado", "path": path, "preview": estrutura[:300] + "..."})

@tool
async def configurar_perfil_autoridade(marca: str, nicho: str, bio: str, pais: str = "BR") -> str:
    """
    FASE 3 — Configura perfil de autoridade completo para redes sociais.
    Entrega: bio otimizada, destaques, estratégia de feed, link na bio.
    """
    return await asyncio.get_event_loop().run_in_executor(None, _invoke,
        f"""Você é especialista em Social Media e construção de autoridade digital.
MARCA: {marca} | NICHO: {nicho} | BIO ATUAL: {bio} | MERCADO: {pais}

CONFIGURAÇÃO DE PERFIL DE AUTORIDADE:
1. BIO OTIMIZADA (Instagram/TikTok — máx 150 chars com emoji e CTA)
2. BIO LINKEDIN (versão profissional expandida)
3. BIO TWITTER/X (versão curta e impactante)
4. NOME DE USUÁRIO SUGERIDO (consistente entre plataformas)
5. DESTAQUES DO INSTAGRAM (5 categorias com nomes)
6. LINK NA BIO (o que colocar e em que ordem no linktree)
7. FOTO DE PERFIL (orientações de estilo e composição)
8. FOTO DE CAPA (orientações para LinkedIn/Facebook/Twitter)
9. ESTRATÉGIA DE FEED (tema visual + frequência)"""
    )

@tool
async def gerar_pagina_vendas(produto: str, preco: str, garantia: str,
                               publico: str, beneficios: str) -> str:
    """
    FASE 3 — Gera página de vendas completa em HTML (loja aberta 24h).
    Inclui checkout simulado e pixel de rastreamento placeholder.
    """
    loop = asyncio.get_event_loop()
    html = await loop.run_in_executor(None, _invoke,
        f"""Você é um copywriter e web designer especialista em páginas de vendas.
PRODUTO: {produto} | PREÇO: {preco} | GARANTIA: {garantia}
PÚBLICO: {publico} | BENEFÍCIOS: {beneficios}

Crie HTML completo de página de vendas com:
- Headline irresistível + video placeholder
- Seção "Para quem é" e "Para quem NÃO é"
- Módulos/benefícios do produto
- Bônus (3 bônus com valor percebido)
- Depoimentos (3 placeholders)
- Garantia visual
- Bloco de preço com desconto + urgência (contador)
- Botão de compra com segurança
- FAQ (5 perguntas)
- Footer com termos

Design profissional, CSS inline, cores de conversão (verde/laranja para CTAs).
Retorne APENAS o HTML."""
    )

    import hashlib, os
    h = hashlib.md5(produto.encode()).hexdigest()[:8]
    path = f"/home/jod_robo/JOD_ROBO/social_sessions/pages/sales_{h}.html"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return json.dumps({"status": "gerado", "path": path, "preview": html[:300] + "..."})

# ══════════════════════════════════════════════════════════════════════════════
# FASE 4 — TRAÇÃO E QUALIFICAÇÃO
# ══════════════════════════════════════════════════════════════════════════════

@tool
async def estrategia_trafego(tipo: str, marca: str, produto: str,
                              orcamento: str, objetivo: str) -> str:
    """
    FASE 4 — Estratégia de tráfego orgânico e/ou pago.
    tipo: 'organico' | 'pago' | 'hibrido'.
    """
    return await asyncio.get_event_loop().run_in_executor(None, _invoke,
        f"""Você é um especialista em tráfego digital (Meta Ads, Google Ads, TikTok Ads, SEO).
MARCA: {marca} | PRODUTO: {produto}
TIPO: {tipo} | ORÇAMENTO: {orcamento} | OBJETIVO: {objetivo}

ESTRATÉGIA DE TRÁFEGO COMPLETA:
{'ORGÂNICO:' if tipo in ['organico','hibrido'] else ''}
{'- SEO: palavras-chave principais + estratégia de conteúdo' if tipo in ['organico','hibrido'] else ''}
{'- Reels/TikTok virais: 3 formatos que mais convertem no nicho' if tipo in ['organico','hibrido'] else ''}
{'- Parcerias e collabs: perfis para abordar' if tipo in ['organico','hibrido'] else ''}
{'PAGO:' if tipo in ['pago','hibrido'] else ''}
{'- Campanha recomendada: objetivo + configuração' if tipo in ['pago','hibrido'] else ''}
{'- Público: interesses + comportamentos + lookalike' if tipo in ['pago','hibrido'] else ''}
{'- Criativos: 3 formatos para testar (A/B)' if tipo in ['pago','hibrido'] else ''}
{'- Orçamento: distribuição diária + escala' if tipo in ['pago','hibrido'] else ''}
- FUNIL COMPLETO: topo → meio → fundo
- MÉTRICAS: CPL alvo, CPA, ROAS mínimo"""
    )

@tool
async def panfletagem_digital(marca: str, produto: str, canais: str, mensagem: str) -> str:
    """
    FASE 4 — Panfletagem digital: distribuição de mensagem em múltiplos canais.
    canais: ex 'whatsapp, grupos, dm instagram, email'.
    Gera templates prontos para cada canal.
    """
    return await asyncio.get_event_loop().run_in_executor(None, _invoke,
        f"""Você é especialista em distribuição de conteúdo e prospecção digital.
MARCA: {marca} | PRODUTO: {produto}
CANAIS: {canais} | MENSAGEM BASE: {mensagem}

Crie templates de panfletagem digital para cada canal:
1. WHATSAPP (abordagem quente — máx 3 linhas + CTA)
2. DM INSTAGRAM (abordagem fria → conexão → oferta)
3. EMAIL (subject matador + body de 150 palavras)
4. GRUPOS/COMUNIDADES (post de valor que leva ao produto)
5. STORIES COM ENQUETE (para captar leads quentes)
6. SEQUÊNCIA DE FOLLOW-UP (3 mensagens caso não responda)

Cada template deve soar HUMANO, não robótico."""
    )

@tool
async def roteiro_engajamento(plataforma: str, objetivo: str, marca: str) -> str:
    """
    FASE 4 — Roteiros de engajamento para crescer organicamente.
    objetivo: 'salvar', 'comentar', 'compartilhar', 'seguir', 'clicar_link'.
    """
    return await asyncio.get_event_loop().run_in_executor(None, _invoke,
        f"""Você é um especialista em engajamento e algoritmos de redes sociais.
MARCA: {marca} | PLATAFORMA: {plataforma} | OBJETIVO: {objetivo}

ROTEIRO DE ENGAJAMENTO:
1. GANCHO que force a ação de {objetivo}
2. CORPO do conteúdo (storytelling + valor)
3. PERGUNTA DE ENGAJAMENTO (que faça as pessoas comentarem)
4. CTA para {objetivo} (natural, não forçado)
5. ESTRATÉGIA DE RESPOSTA (como responder os primeiros comentários para bombar o algoritmo)
6. MELHOR HORÁRIO para postar em {plataforma}
7. FREQUÊNCIA ideal para manter o alcance crescendo"""
    )

@tool
async def triagem_interessados(produto: str, preco: str, perguntas_qualificacao: str) -> str:
    """
    FASE 4 — Triagem de interessados: filtra curiosos antes da oferta.
    Cria script de qualificação que só deixa passar leads prontos para comprar.
    """
    return await asyncio.get_event_loop().run_in_executor(None, _invoke,
        f"""Você é um especialista em qualificação de leads e vendas consultivas.
PRODUTO: {produto} | PREÇO: {preco}
CRITÉRIOS: {perguntas_qualificacao}

SISTEMA DE TRIAGEM COMPLETO:
1. MENSAGEM DE ENTRADA (quando o lead chega pela 1ª vez)
2. PERGUNTAS DE QUALIFICAÇÃO (em ordem — do mais simples ao decisivo):
   Q1: (verifica interesse real)
   Q2: (verifica capacidade financeira sem ser direto)
   Q3: (verifica urgência/dor)
   Q4: (verifica poder de decisão)
3. CRITÉRIOS DE APROVAÇÃO (quem passa para a oferta)
4. CRITÉRIOS DE ELIMINAÇÃO (quem não passa — com mensagem gentil)
5. TRANSIÇÃO PARA OFERTA (frase de ponte para apresentar o produto)
6. SCRIPT COMPLETO EM FLUXO (copie e use no WhatsApp/chatbot)"""
    )

# ══════════════════════════════════════════════════════════════════════════════
# FASE 5 — CONVERSÃO E RECUPERAÇÃO DE CAIXA
# ══════════════════════════════════════════════════════════════════════════════

@tool
async def oferta_direta_qualificados(produto: str, preco: str,
                                      bonus: str, urgencia: str) -> str:
    """
    FASE 5 — Oferta direta para leads que passaram na triagem.
    Gera script de apresentação de oferta irresistível.
    """
    return await asyncio.get_event_loop().run_in_executor(None, _invoke,
        f"""Você é um closer de vendas de alto ticket especialista em ofertas irresistíveis.
PRODUTO: {produto} | PREÇO: {preco}
BÔNUS: {bonus} | URGÊNCIA: {urgencia}

SCRIPT DE OFERTA DIRETA:
1. TRANSIÇÃO (como entrar na oferta após a triagem)
2. APRESENTAÇÃO DO PRODUTO (benefício + transformação em 30 segundos)
3. STACK DE VALOR (produto + bônus + suporte = valor total percebido)
4. REVELAÇÃO DO PREÇO (ancoragem + desconto + justificativa)
5. GARANTIA (eliminar todo risco de compra)
6. URGÊNCIA REAL (por que agir AGORA)
7. FECHAMENTO (pergunta de comprometimento)
8. TRATAMENTO DE SILÊNCIO (o que fazer se não responder)
9. VERSÕES: WhatsApp | Email | Vídeo de vendas"""
    )

@tool
async def script_remarketing(produto: str, motivo_nao_compra: str, oferta_recuperacao: str) -> str:
    """
    FASE 5 — Remarketing: recupera quem viu a oferta e não comprou.
    motivo_nao_compra: 'preco', 'duvida', 'tempo', 'concorrente', 'esqueceu'.
    """
    return await asyncio.get_event_loop().run_in_executor(None, _invoke,
        f"""Você é especialista em remarketing e recuperação de vendas perdidas.
PRODUTO: {produto}
MOTIVO PROVÁVEL DA NÃO COMPRA: {motivo_nao_compra}
OFERTA DE RECUPERAÇÃO: {oferta_recuperacao}

SEQUÊNCIA DE REMARKETING (7 dias):
Dia 1 (2h após abandono): (mensagem de valor, não de venda)
Dia 2: (prova social — depoimento de quem comprou)
Dia 3: (quebra da objeção principal: {motivo_nao_compra})
Dia 4: (bônus surpresa só para quem não comprou ainda)
Dia 5: (urgência real — vagas/tempo limitado)
Dia 6: (história de transformação de um cliente)
Dia 7: (última chance — oferta final com escassez)

Para cada dia: canal (email/whatsapp/anúncio) + mensagem completa pronta."""
    )

@tool
async def automacao_atendimento_vendas(marca: str, produto: str,
                                        faq_respostas: str) -> str:
    """
    FASE 5 — Automação de atendimento e vendas: fluxo completo de chatbot.
    Gera script de automação para WhatsApp/Instagram DM/site.
    """
    return await asyncio.get_event_loop().run_in_executor(None, _invoke,
        f"""Você é especialista em automação de atendimento e chatbots de vendas.
MARCA: {marca} | PRODUTO: {produto}
FAQ: {faq_respostas}

FLUXO DE AUTOMAÇÃO COMPLETO:
1. MENU INICIAL (opções: saber mais / já cliente / falar com humano)
2. FLUXO DE INTERESSE (lead frio → qualificado):
   Mensagem 1 → aguarda → Mensagem 2 → ...
3. RESPOSTAS AUTOMÁTICAS para as 10 perguntas mais comuns
4. FLUXO DE VENDA (qualificado → oferta → checkout)
5. FLUXO PÓS-COMPRA (boas-vindas + onboarding + upsell)
6. GATILHOS DE ESCALAÇÃO (quando passa para humano)
7. HORÁRIOS DE FUNCIONAMENTO (mensagem fora do horário)
8. CONFIGURAÇÃO RECOMENDADA (ManyChat / Typebot / Z-API)"""
    )

@tool
async def automacao_checkout(produto: str, preco: str, plataforma_pagamento: str) -> str:
    """
    FASE 5 — Automação de checkout: fecha a venda automaticamente.
    plataforma_pagamento: 'hotmart' | 'kiwify' | 'monetizze' | 'stripe' | 'mercadopago'.
    """
    return await asyncio.get_event_loop().run_in_executor(None, _invoke,
        f"""Você é especialista em otimização de checkout e recuperação de carrinho.
PRODUTO: {produto} | PREÇO: {preco} | PLATAFORMA: {plataforma_pagamento}

AUTOMAÇÃO DE CHECKOUT COMPLETA:
1. CONFIGURAÇÃO DO CHECKOUT (campos, layout, 1 página vs multi-step)
2. ORDER BUMP (oferta complementar no checkout — o que oferecer)
3. UPSELL PÓS-COMPRA (oferta imediata após confirmar pagamento)
4. RECUPERAÇÃO DE BOLETO/PIX não pago:
   - 1h após: mensagem 1
   - 24h após: mensagem 2
   - 48h após: mensagem 3 (urgência)
5. RECUPERAÇÃO DE CARTÃO RECUSADO
6. EMAIL DE CONFIRMAÇÃO (template pronto)
7. SEQUÊNCIA DE ONBOARDING (3 emails pós-compra)
8. WEBHOOK DE INTEGRAÇÃO (como conectar ao n8n para automação total)"""
    )

# ══════════════════════════════════════════════════════════════════════════════
# EXPORT — todos os tools das 5 fases
# ══════════════════════════════════════════════════════════════════════════════

FASE1_TOOLS = [atendimento_24h, agenda_pessoal, posicionamento_nicho]

FASE2_TOOLS = [reuniao_equipe_conteudo, roteiro_conteudo,
               storytelling_personal_branding, copywriting_produto, growth_estrategias]

FASE3_TOOLS = [gerar_identidade_visual, gerar_landing_page,
               configurar_perfil_autoridade, gerar_pagina_vendas]

FASE4_TOOLS = [estrategia_trafego, panfletagem_digital,
               roteiro_engajamento, triagem_interessados]

FASE5_TOOLS = [oferta_direta_qualificados, script_remarketing,
               automacao_atendimento_vendas, automacao_checkout]

ALL_ELI_TOOLS = FASE1_TOOLS + FASE2_TOOLS + FASE3_TOOLS + FASE4_TOOLS + FASE5_TOOLS
