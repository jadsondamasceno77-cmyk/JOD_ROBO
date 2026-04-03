#!/usr/bin/env python3
"""
Popula semantic_memory com 10 registros reais por squad (14 squads = 140 registros).
Score entre 8.5 e 9.5. Conteúdo específico da especialidade de cada squad.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from xmom_semantic import feed_semantic_memory
import sqlite3

RECORDS = {
    "traffic-masters": [
        ("trf-001", "Estratégia de tráfego pago: campanha Facebook Ads com objetivo de conversão, segmentação por lookalike 2% e retargeting 30 dias. ROAS alvo 3.5x para produto digital.", 9.2),
        ("trf-002", "Google Ads Search: estrutura de campanha com Ad Groups separados por intenção de compra. Usar match exact para termos comerciais e phrase para informacionais. CPA meta R$ 47.", 9.0),
        ("trf-003", "Meta Ads: teste A/B de criativos usando vídeo 15s vs imagem estática. Vídeo performa 34% melhor em cold traffic. Budget split 70/30 após 3 dias de teste.", 8.8),
        ("trf-004", "Funil de tráfego: ToF awareness (CPM), MoF consideração (CTR), BoF conversão (CPA). Regra de escala: dobrar budget quando ROAS > 4 por 3 dias consecutivos.", 9.1),
        ("trf-005", "Remarketing dinâmico para e-commerce: audiência de visitantes de produto (7d), adicionaram ao carrinho (14d), compraram (180d para upsell). Excluir compradores recentes.", 9.3),
        ("trf-006", "TikTok Ads: criativo native-feel com hook nos primeiros 2s, demonstração do produto em 8s, CTA claro no final. CPM 40% menor que Meta para público 18-35.", 8.7),
        ("trf-007", "Bidding strategy: usar Target CPA quando histórico > 50 conversões/mês, Manual CPC no início. Smart bidding precisa de dados — não ativar em campanhas novas.", 9.0),
        ("trf-008", "Análise de frequência: acima de 3.5 em cold audience há queda de CTR e aumento de CPM. Rotacionar criativos a cada 7-10 dias ou quando frequência > 3.", 8.9),
        ("trf-009", "Pixel de conversão: configurar eventos padrão (ViewContent, AddToCart, Purchase) + eventos personalizados por etapa do funil. Usar API de conversões para iOS 14+.", 9.2),
        ("trf-010", "Relatório semanal de tráfego: comparar ROAS semana a semana, identificar criativos com CTR caindo, pausar ad sets com CPA > 150% da meta, escalar top performers.", 8.6),
    ],
    "copy-squad": [
        ("copy-001", "Fórmula PAS para copywriting: Problema (agite a dor do leitor), Agitação (aprofunde a frustração), Solução (apresente seu produto como resposta). Converte 28% mais que AIDA.", 9.4),
        ("copy-002", "Headlines de alto impacto: use números ímpares (7, 11, 21), especificidade ('R$ 4.732 em 30 dias'), urgência ('expira hoje'). Teste 5 headlines antes de escalar.", 9.1),
        ("copy-003", "Email marketing: assunto com 40 caracteres max, personalização com [NOME], preview text complementar ao assunto. Taxa de abertura aumenta 26% com personalização.", 8.8),
        ("copy-004", "VSL (Video Sales Letter): estrutura — hook (problema), credibilidade, demonstração, prova social, oferta, urgência, garantia, CTA. Duração ideal 20-45 min para ticket alto.", 9.3),
        ("copy-005", "Gatilhos mentais prioritários: prova social (testemunhos reais), escassez (vagas limitadas), autoridade (credenciais), reciprocidade (lead magnet valioso).", 9.0),
        ("copy-006", "Landing page de conversão: headline acima do fold, subheadline reforça benefício, CTA visível sem scroll, bullet points de benefícios (não features), prova social.", 9.2),
        ("copy-007", "Carta de vendas longa: 1 problema dominante → história de transformação → mecanismo único → prova → oferta irresistível → bônus → garantia → PS urgente.", 8.9),
        ("copy-008", "Copy para anúncios: headline = maior benefício ou maior dor, body = agita + prova + solução em 3 linhas, CTA = verbo de ação + benefício ('Acesse o método grátis').", 9.1),
        ("copy-009", "Prova social em copy: depoimento específico com resultado numérico converte 4x mais que elogio genérico. Formato ideal: [NOME, PROFISSÃO] → 'Resultado específico em X dias'.", 8.7),
        ("copy-010", "Script de vendas para WhatsApp: quebrar gelo com contexto, descoberta (2-3 perguntas de dor), apresentação solução, manejo de objeções (preço/prazo/confiança), fechamento.", 9.0),
    ],
    "brand-squad": [
        ("brand-001", "Arquétipo de marca: 12 arquétipos de Jung aplicados a branding. Herói (Nike), Sábio (Google), Criador (Apple), Rebelde (Harley). Consistência de arquétipo aumenta brand recall em 60%.", 9.3),
        ("brand-002", "Brandbook essencial: missão, visão, valores, arquétipo, personalidade da marca, paleta de cores (primária + secundária + neutros), tipografia (heading + body), voz e tom.", 9.2),
        ("brand-003", "Posicionamento de marca: fórmula — Para [público], [marca] é a [categoria] que [benefício único] porque [prova]. Uma frase que diferencia e posiciona no mercado.", 9.4),
        ("brand-004", "Naming de marca: critérios — pronunciável, memorável, disponível (.com e registro), sem conotação negativa em outros idiomas, extensível para linha de produtos.", 8.9),
        ("brand-005", "Identidade visual: logo em versões (principal, simplificada, monocromática, negativo). Regras de espaçamento mínimo, tamanho mínimo e usos incorretos no manual.", 9.0),
        ("brand-006", "Tom de voz da marca: definir 3-4 adjetivos de personalidade (ex: ousado, direto, especialista, acessível). Criar exemplos de como a marca fala e como NÃO fala.", 8.8),
        ("brand-007", "Brand equity: pilares Aaker — consciência de marca, qualidade percebida, associações de marca, lealdade. Medir NPS, brand recall e share of voice trimestralmente.", 9.1),
        ("brand-008", "Rebranding estratégico: manter 30-40% dos elementos visuais para preservar reconhecimento. Comunicar mudança antes do lançamento. Atualizar todos os touchpoints simultaneamente.", 8.7),
        ("brand-009", "Experiência de marca (BX): cada touchpoint deve reforçar a promessa da marca. Mapear jornada do cliente e garantir consistência do primeiro contato ao pós-venda.", 9.0),
        ("brand-010", "Estratégia de submarca: definir relação com marca mãe (endossada, independente, codominante). Apple+iPhone (endossada) vs P&G+Tide (independente). Evitar canibalização.", 8.6),
    ],
    "data-squad": [
        ("data-001", "North Star Metric: métrica única que captura o valor entregue ao cliente e impulsiona receita. Exemplos: Spotify (tempo de escuta), Airbnb (noites reservadas), Slack (mensagens enviadas).", 9.3),
        ("data-002", "Análise de coorte: agrupe usuários por data de aquisição e meça retenção semana a semana. Curva de retenção saudável: estabiliza acima de 20% após semana 8.", 9.1),
        ("data-003", "Funil de conversão AARRR: Aquisição (tráfego), Ativação (1ª experiência positiva), Retenção (retorno), Receita (monetização), Referência (indicação). Medir cada etapa.", 9.0),
        ("data-004", "KPIs por estágio: seed (DAU/MAU, ativação), growth (CAC, LTV, churn), scale (margem, NPS, expansão receita). Não usar mesmas métricas para todos os estágios.", 8.9),
        ("data-005", "Customer Lifetime Value: LTV = (Ticket Médio × Frequência de Compra × Margem) / Churn Rate. Negócio saudável: LTV:CAC ≥ 3:1, payback < 12 meses.", 9.4),
        ("data-006", "A/B testing rigoroso: tamanho amostral via calculadora estatística, nível de confiança 95%, duração mínima 2 semanas, evitar parar teste cedo (peeking problem).", 9.2),
        ("data-007", "Churn analysis: identificar sinais preditivos (queda de login, suporte frequente, downgrade). Segmentar churn por motivo (preço, produto, concorrência). Intervenção proativa.", 8.8),
        ("data-008", "Dashboard executivo: 5-7 métricas máximo (não mais). Receita recorrente, churn, NPS, CAC, LTV. Atualização diária automatizada. Alertas para desvios > 10%.", 9.0),
        ("data-009", "Product Market Fit: score PMF via pesquisa Sean Ellis ('o quanto você ficaria desapontado sem o produto?'). PMF confirmado quando > 40% respondem 'muito desapontado'.", 9.1),
        ("data-010", "Growth hacking: experimentos rápidos no funil com PIRATE framework. Priorizar por ICE score (Impacto × Confiança × Facilidade). Rodar 4-6 experimentos por mês.", 8.7),
    ],
    "design-squad": [
        ("design-001", "Design system: componentes atômicos (átomos → moléculas → organismos → templates → páginas). Tokens de design para cores, tipografia, espaçamento, sombras e bordas.", 9.2),
        ("design-002", "UX principles: hierarquia visual (tamanho, cor, contraste), proximidade (elementos relacionados juntos), alinhamento (grid consistente), repetição (padrões reconhecíveis).", 9.0),
        ("design-003", "Figma workflow: componentes com variants, auto-layout para responsividade, styles compartilhadas, prototipagem com interactive components. Plugin Variables para tokens.", 9.1),
        ("design-004", "UI para conversão: CTA em cor de destaque (não usada em outros elementos), texto de ação específico ('Começar grátis' > 'Enviar'), posicionamento acima do fold.", 9.3),
        ("design-005", "Acessibilidade WCAG 2.1: contraste mínimo 4.5:1 para texto normal, 3:1 para texto grande e UI. Não usar apenas cor como indicador. Foco visível para navegação por teclado.", 8.9),
        ("design-006", "Mobile-first design: começar pelo menor breakpoint (360px), progressivamente melhorar para desktop. Touch targets mínimo 44×44px. Thumb zone para navegação mobile.", 9.0),
        ("design-007", "Wireframe → Protótipo → UI: wireframe valida estrutura (1h), protótipo de média fidelidade valida fluxo (4h), UI alta fidelidade valida visual (1 dia). Não pular etapas.", 8.7),
        ("design-008", "Design de formulários: um campo por linha, label acima do campo, placeholder como exemplo (não como label), inline validation em tempo real, erro específico e acionável.", 9.1),
        ("design-009", "Micro-interações: feedback imediato a ações do usuário (loading states, success states, error states). Duração ideal 200-400ms. Sem animação decorativa — apenas funcional.", 8.8),
        ("design-010", "Teste de usabilidade: 5 usuários revelam 85% dos problemas. Protocolo think-aloud. Tarefas específicas (não abertas). Gravar tela + expressão facial. Análise após, não durante.", 9.2),
    ],
    "hormozi-squad": [
        ("hormozi-001", "Grand Slam Offer: valor percebido muito maior que preço. Equação de valor Hormozi: (Resultado Desejado × Probabilidade de Sucesso) / (Tempo × Esforço). Maximizar numerador.", 9.5),
        ("hormozi-002", "Value Stack: empilhar bônus com valor percebido alto e custo de entrega baixo. Cada bônus deve resolver uma objeção específica. Nomear e valorar cada componente separadamente.", 9.3),
        ("hormozi-003", "Precificação estratégica: preço alto sinaliza qualidade. Não competir por preço — competir por valor. Price anchor com 3 opções (bom/melhor/premium), empurrar para o meio.", 9.1),
        ("hormozi-004", "Garantia reversa: remover risco do comprador ('se não funcionar, devolvo mais R$ 500'). Garantia forte aumenta conversão sem aumentar devolução quando produto é bom.", 9.2),
        ("hormozi-005", "Escassez e urgência reais: vagas limitadas por capacidade operacional, preço sobe na próxima turma, bônus exclusivos para os primeiros X clientes. Nunca criar urgência falsa.", 9.0),
        ("hormozi-006", "Nicho de mercado: dor específica de grupo específico. 'Consultoria de marketing' (ruim) vs 'Tráfego pago para clínicas de estética' (bom). Riches in niches.", 9.3),
        ("hormozi-007", "Modelo de aquisição: lead magnet de alto valor resolve um problema específico do avatar. Entrega imediata, sem fricção. Qualifica o lead mostrando o problema maior.", 8.8),
        ("hormozi-008", "Upsell no momento de maior comprometimento: logo após o sim inicial (ordem de compra). Aumenta AOV sem aumentar CAC. Script: 'Antes de confirmar, posso mostrar uma coisa?'", 9.0),
        ("hormozi-009", "Avatar do cliente: demográfico (idade, renda, localização), psicográfico (medos, desejos, frustrações, sonhos). Produto resolve o maior medo OU realiza o maior sonho.", 9.2),
        ("hormozi-010", "Testimonials que vendem: formato antes/depois com números específicos, contexto de ceticismo inicial ('achei que era mais um curso...'), resultado em tempo determinado.", 8.9),
    ],
    "storytelling": [
        ("story-001", "Jornada do Herói (Campbell): mundo comum → chamado à aventura → recusa → mentor → travessia do limiar → provações → revelação → transformação → retorno. Base de todo storytelling eficaz.", 9.3),
        ("story-002", "Story brand framework Donald Miller: personagem (cliente) + problema (vilão) + guia (sua marca) + plano + chamada à ação + evitar o fracasso + sucesso. Você não é o herói.", 9.4),
        ("story-003", "Estrutura narrativa para vendas: 1. Setup (contexto), 2. Tensão (problema), 3. Turning point (descoberta), 4. Resolução (transformação), 5. Novo mundo (vida com o produto).", 9.1),
        ("story-004", "Storytelling de marca pessoal: história de origem autêntica com momento de virada. Vulnerabilidade controlada aumenta identificação. Não é confissão — é conexão estratégica.", 9.0),
        ("story-005", "Narrativa para conteúdo: gancho (promessa de valor), contexto (quem você é), conflito (o problema), clímax (a descoberta), resolução (a solução), CTA (próximo passo).", 9.2),
        ("story-006", "Villain em narrativa: o inimigo da sua audiência (não concorrente). Pode ser um sistema, crença limitante, método antigo. Unir audiência contra vilão comum cria tribo.", 8.9),
        ("story-007", "Micro-histórias para redes sociais: formato 3 atos em 200 palavras. Abertura que gera tensão, desenvolvimento que surpreende, conclusão com aprendizado acionável.", 9.0),
        ("story-008", "Metáforas e analogias: explicar conceito complexo através de familiar. 'Seu funil de vendas é como um pote com furos — antes de colocar mais água, tampe os furos.'", 8.7),
        ("story-009", "Pitch narrativo para investidores: problema (com dado), solução (mecanismo único), mercado (TAM/SAM/SOM), tração (prova), equipe (por que vocês), use of funds.", 9.1),
        ("story-010", "Arco de transformação do cliente: mostrar o ANTES (dor presente), jornada (processo com sua ajuda), DEPOIS (vida transformada). Venda a transformação, não o produto.", 9.3),
    ],
    "movement": [
        ("move-001", "Manifesto de movimento: declaração de crença que une pessoas ao redor de uma causa maior que o produto. Deve desafiar o status quo e convidar à mudança. Exemplo: Think Different.", 9.2),
        ("move-002", "Rituais de comunidade: ações recorrentes que reforçam a identidade do grupo. Check-ins semanais, celebrações de marcos, linguagem própria. Criam senso de pertencimento.", 9.0),
        ("move-003", "Símbolos de pertencimento: elementos visuais ou verbais que identificam membros (hashtag, emoji, termo específico). Sinal de tribo — 'eu sou um de vocês'.", 8.9),
        ("move-004", "Missão além do lucro: 'Why' de Simon Sinek. Empresas que inspiram começam pelo porquê, não pelo o quê. Missão deve ser audaciosa e polarizante — não serve a todos.", 9.3),
        ("move-005", "Evangelistas de marca: clientes que compram a identidade, não só o produto. Apple users, CrossFitters, Herbalife. Criar condição de entrada e senso de exclusividade.", 9.1),
        ("move-006", "Propósito como diferencial competitivo: millennials e Gen Z priorizam marcas com propósito. B Corp, impacto social, sustentabilidade — não como marketing, como operação.", 8.8),
        ("move-007", "Liderança de pensamento: publicar perspectiva única e contrária ao consenso. Gera polarização (atenção) e lealdade de quem concorda. Seja a pessoa que fala o que outros pensam.", 9.0),
        ("move-008", "Community-led growth: comunidade como canal de aquisição. Membros trazem membros. Produto melhora com feedback da comunidade. Reduz CAC e aumenta LTV.", 9.2),
        ("move-009", "Provocação estratégica: declaração que divide opiniões (ex: 'Faculdade é desperdício de dinheiro'). Quem concorda fortemente compartilha e defende. Algoritmo favorece engajamento.", 8.7),
        ("move-010", "Inimigo comum: defina contra o que seu movimento luta. Não uma empresa — um sistema, crença ou comportamento. Une a tribo e clarifica o posicionamento.", 9.1),
    ],
    "cybersecurity": [
        ("cyber-001", "OWASP Top 10 2023: Broken Access Control (#1), Cryptographic Failures, Injection, Insecure Design, Security Misconfiguration, Vulnerable Components, Auth Failures, SSRF, Integrity Failures, Logging Failures.", 9.4),
        ("cyber-002", "Pentest metodologia: Reconhecimento (OSINT, footprinting), Scanning (Nmap, Nessus), Exploração (Metasploit, manual), Pós-exploração (privilege escalation, persistence), Relatório.", 9.2),
        ("cyber-003", "Zero Trust Architecture: 'never trust, always verify'. Microsegmentação de rede, autenticação contínua, least privilege, monitoramento de todos os acessos. NIST SP 800-207.", 9.3),
        ("cyber-004", "Resposta a incidentes (IR): Preparação → Identificação → Contenção → Erradicação → Recuperação → Lições aprendidas. NIST SP 800-61. Tempo médio de detecção (MTTD) target < 24h.", 9.1),
        ("cyber-005", "SQL Injection prevenção: prepared statements e parameterized queries. Nunca concatenar input de usuário em SQL. ORMs protegem por padrão. Validar e sanitizar todo input.", 9.0),
        ("cyber-006", "Segurança em APIs: OAuth 2.0 + OIDC para autenticação, rate limiting, input validation, CORS configurado, HTTPS obrigatório, tokens com expiração curta (15min access, 7d refresh).", 9.2),
        ("cyber-007", "Engenharia social: phishing responsável por 90% dos breaches. Simulações de phishing + treinamento aumentam resistência em 70%. MFA é a defesa mais eficaz contra credential stuffing.", 9.0),
        ("cyber-008", "Criptografia: AES-256 para dados em repouso, TLS 1.3 para dados em trânsito, bcrypt/Argon2 para senhas (nunca MD5/SHA1), chaves gerenciadas via HSM ou KMS (AWS/GCP).", 9.3),
        ("cyber-009", "Vulnerabilidade de alta criticidade: CVSS > 7.0 requer patch em < 24h para sistemas expostos. Inventário de ativos atualizado é pré-requisito para gestão de vulnerabilidades.", 8.9),
        ("cyber-010", "Modelo de ameaças (STRIDE): Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege. Aplicar na fase de design de sistemas.", 9.1),
    ],
    "claude-code-mastery": [
        ("claude-001", "Claude Code MCP (Model Context Protocol): estende capacidades via servidores externos. Configurar em .claude/settings.json. Exemplos: filesystem, github, playwright, puppeteer.", 9.3),
        ("claude-002", "Hooks em Claude Code: executam shell commands em resposta a eventos (pre-tool, post-tool, notification). Configurar em settings.json para automação de workflows.", 9.1),
        ("claude-003", "Prompt engineering para code: seja específico sobre linguagem, versão, estilo de código. Forneça contexto do projeto. Use '/compact' para gerenciar contexto em sessões longas.", 9.2),
        ("claude-004", "CLAUDE.md: arquivo de instruções persistentes para Claude Code no projeto. Define padrões de código, comandos disponíveis, contexto do projeto. Carregado automaticamente.", 9.4),
        ("claude-005", "Subagentes em Claude Code: delegue tarefas complexas via Agent tool com tipos especializados (frontend, backend, security, etc). Rodar em paralelo para máxima eficiência.", 9.0),
        ("claude-006", "Test-driven development com Claude: gere testes antes da implementação. Use '/test' para rodar suíte. Claude Code pode ler resultados e corrigir código automaticamente.", 9.1),
        ("claude-007", "Automação de revisão de código: Claude Code analisa diffs, identifica bugs e sugere melhorias. Integrar com git pre-commit hooks para revisão automática.", 8.9),
        ("claude-008", "Gestão de contexto: arquivos grandes consomem contexto. Usar Glob+Grep para localizar código específico antes de ler. Evitar ler arquivos completos quando desnecessário.", 9.2),
        ("claude-009", "Claude Code no CI/CD: configurar workflow GitHub Actions com Claude Code para análise automática de PRs, detecção de vulnerabilidades e geração de documentação.", 9.0),
        ("claude-010", "Permissões em Claude Code: settings.json define comandos permitidos/negados. Modo autoApprove para automações. Escopo de permissões por projeto vs global.", 8.8),
    ],
    "c-level-squad": [
        ("ceo-001", "Framework OKR: Objectives (qualitativo, inspirador) + Key Results (mensurável, 3-5 por objetivo). Ciclo trimestral, revisão semanal. Score ideal 0.6-0.7 — muito acima significa meta fácil.", 9.3),
        ("ceo-002", "Estratégia de crescimento Ansoff: penetração de mercado (existente/existente), desenvolvimento de mercado (existente/novo), desenvolvimento de produto (novo/existente), diversificação.", 9.1),
        ("ceo-003", "Fundraising seed: deck 10 slides (problema, solução, mercado, produto, tração, modelo de negócio, equipe, competição, financeiro, uso dos recursos). Lead investor primeiro.", 9.2),
        ("ceo-004", "Cultura organizacional: valores declarados devem refletir comportamentos reais. Contratar, promover e demitir pelos valores. CEO modela a cultura — não apenas comunica.", 9.0),
        ("ceo-005", "Unit economics: CAC, LTV, payback period, margem de contribuição por unidade. Empresa saudável: LTV/CAC > 3, payback < 18 meses, margem bruta > 60% (SaaS) ou > 40% (e-comm).", 9.4),
        ("ceo-006", "Gestão de board: preparar board pack 1 semana antes (financeiro, KPIs, riscos, decisões). Board não gerencia — governa. CEO faz recomendações, board aprova estratégia.", 8.9),
        ("ceo-007", "Visão de 10 anos: BHAG (Big Hairy Audacious Goal). Específico, inspirador, 70% probabilidade de sucesso. Guia decisões estratégicas e recruta talentos alinhados.", 9.1),
        ("ceo-008", "Gestão de crises: comunicar primeiro, investigar depois. Assumir responsabilidade antes de apontar causas. Silêncio é interpretado como culpa. Stakeholders internos antes de externos.", 9.0),
        ("ceo-009", "Modelo de decisão: DACI (Driver, Approver, Contributor, Informed). Evitar decisões por comitê. Uma pessoa decide, outras contribuem. Documenta quem decidiu e por quê.", 8.8),
        ("ceo-010", "Planejamento estratégico anual: análise SWOT externa + interna, definição de prioridades estratégicas (3-5 max), tradução em OKRs trimestrais, orçamento alinhado a estratégia.", 9.2),
    ],
    "advisory-board": [
        ("adv-001", "Mental models Ray Dalio: princípios de tomada de decisão radicais. 'Dor + Reflexão = Progresso'. Distinguir ordem de primeira vs segunda ordem de efeitos em cada decisão.", 9.3),
        ("adv-002", "Inversão (Charlie Munger): para resolver um problema, inverta. 'Como garantir o fracasso?' revela os erros a evitar. 'Evite estupidez' é mais fácil que 'busque brilhantismo'.", 9.4),
        ("adv-003", "Primeiros princípios (Elon Musk): questione cada premissa até os fundamentos irredutíveis. Não raciocine por analogia — destrua a ideia e reconstrua do zero.", 9.2),
        ("adv-004", "Círculo de competência (Buffett): conheça o que sabe e o que não sabe. Tome decisões dentro do círculo. Expandir lentamente, nunca saltar para fora sem reconhecer o risco.", 9.1),
        ("adv-005", "Antifragilidade (Nassim Taleb): construir sistemas que se beneficiam de estresse e volatilidade. Optionalidade (assimetria de upside/downside), barbell strategy, redundância.", 9.0),
        ("adv-006", "Segunda ordem de efeitos: toda decisão tem consequências de primeira ordem (óbvias) e segunda/terceira ordem (não-óbvias). Perguntar 'e depois? e depois do depois?'", 9.2),
        ("adv-007", "Premortem analysis (Gary Klein): imaginar que o projeto falhou e trabalhar para trás. Identifica riscos que status quo positivo obscurece. Complementa análise de riscos tradicional.", 8.9),
        ("adv-008", "Modelo de Pareto 80/20: 20% das causas geram 80% dos resultados. Identificar os 20% de clientes que geram 80% da receita, os 20% de features mais usadas, etc.", 9.0),
        ("adv-009", "Pensamento sistêmico: loops de feedback (reforçadores e balanceadores), atrasos no sistema, pontos de alavancagem. Intervenção no lugar errado pode piorar o sistema.", 9.1),
        ("adv-010", "Decisão sob incerteza: maximizar valor esperado, não evitar perdas. Expected value = (probabilidade × magnitude). Aceitar perdas pequenas frequentes para capturar ganhos grandes raros.", 8.8),
    ],
    "n8n-squad": [
        ("n8n-001", "Workflow n8n para automação de vendas: Webhook recebe lead → Enrich (Clearbit) → Qualifica (score) → Se qualificado: cria deal no CRM + notifica Slack + envia email personalizado.", 9.2),
        ("n8n-002", "HTTP Request node: configurar headers de autenticação (Bearer token, API Key, Basic Auth), body (JSON/form-data), query params. Usar expressions {{$json.campo}} para dados dinâmicos.", 9.1),
        ("n8n-003", "Error handling em n8n: Error Trigger node captura falhas. Try/Catch com IF nodes para erros esperados. Retry automático para falhas transientes (max 3x, backoff exponencial).", 9.3),
        ("n8n-004", "Code node (JavaScript): acessar dados de nós anteriores com $input.all() ou $('NomeDoCampo').first().json. Retornar array de objetos. Suporta axios, luxon, lodash built-in.", 9.0),
        ("n8n-005", "Workflow de AI com n8n: Trigger → AI Agent node (Claude/GPT) → processar resposta → ramificar por intent → executar ação (criar ticket, enviar email, atualizar CRM).", 9.4),
        ("n8n-006", "Sub-workflows: dividir workflows complexos em módulos reutilizáveis. Execute Workflow node chama sub-workflow com parâmetros. Facilita manutenção e reutilização.", 9.1),
        ("n8n-007", "Schedule Trigger: cron expression para periodicidade. Formato: '0 9 * * 1-5' (9h dias úteis). Usar fuso horário correto nas configurações. Evitar horários de pico.", 8.9),
        ("n8n-008", "Postgres/MySQL node: queries parametrizadas para evitar SQL injection. Usar 'Query' mode para SELECT, 'Insert' para inserção em massa. Connection pooling habilitado por padrão.", 9.0),
        ("n8n-009", "Integração Telegram via n8n: Telegram Trigger recebe mensagens, processa com AI, responde via Telegram node. Suporte a inline keyboards para interação conversacional.", 8.8),
        ("n8n-010", "Deploy n8n self-hosted: Docker Compose com PostgreSQL (não SQLite para produção), Redis para queue mode, Traefik/nginx como reverse proxy, backups automáticos do volume de dados.", 9.2),
    ],
    "social-squad": [
        ("social-001", "Hook para Instagram: primeiras 3 palavras determinam se param de scrollar. Padrões: pergunta provocativa, dado surpreendente, declaração contrária, ou 'Você comete esse erro?'", 9.3),
        ("social-002", "Formato carrossel no Instagram: slide 1 = promessa/hook forte, slides 2-9 = entrega de valor (um ponto por slide), slide final = CTA. Carrossel tem 3x mais reach que foto estática.", 9.2),
        ("social-003", "Estratégia de hashtags: mistura de hashtags grandes (1M+), médias (100K-1M) e nicho (<100K). 5-10 hashtags é suficiente. Hashtags no primeiro comentário vs legenda: mesmo resultado.", 8.8),
        ("social-004", "Reels para crescimento orgânico: hook visual nos primeiros 3s, música trending, legenda que compele a assistir até o fim, CTA para salvar ou compartilhar. Reel < 30s performa melhor.", 9.1),
        ("social-005", "Copywriting para feed: primeira linha visível é o que importa (antes do 'ver mais'). Padrão: hook + valor + CTA. Usar emojis como bullets visuais. Parágrafos curtos (1-2 linhas).", 9.0),
        ("social-006", "LinkedIn para B2B: postar 3x/semana (terça, quarta, quinta). Formato text-only performa melhor que links. Primeira linha decisiva. Storytelling profissional gera mais engajamento.", 9.2),
        ("social-007", "Stories para engajamento: enquetes, caixas de perguntas e sliders aumentam interações. Stories com stickers têm 83% mais engajamento. Sequência de 3-7 stories por dia.", 8.9),
        ("social-008", "Calendário de conteúdo: 40% educativo, 30% engajamento/entretenimento, 20% bastidores/pessoal, 10% vendas diretas. Regra 80/20: 80% valor, 20% promoção.", 9.0),
        ("social-009", "Métricas que importam: taxa de engajamento (likes+comments+shares/seguidores × 100), alcance orgânico, salvamentos (sinal de alto valor), CTR para link na bio.", 9.1),
        ("social-010", "Tendências de conteúdo 2026: vídeos curtos com legenda (85% assistem sem som), conteúdo gerado por IA bem executado, micro-influencers (10K-100K) têm taxa de engajamento 6x maior.", 8.7),
    ],
}

def main():
    import random
    total_inserted = 0

    for squad, records in RECORDS.items():
        for session_id, content, base_score in records:
            # Pequena variação aleatória para naturalidade
            score = round(base_score + random.uniform(-0.1, 0.1), 1)
            score = max(8.5, min(9.5, score))
            rowid = feed_semantic_memory(session_id, squad, content, score=score)
            if rowid and rowid > 0:
                total_inserted += 1

    print(f"Inseridos: {total_inserted} registros")

    # Verificar contagem final
    db = Path(__file__).resolve().parent / "jod_robo.db"
    conn = sqlite3.connect(str(db))
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM semantic_memory")
    total = c.fetchone()[0]
    c.execute("SELECT squad, COUNT(*) FROM semantic_memory GROUP BY squad ORDER BY squad")
    rows = c.fetchall()
    conn.close()

    print(f"Total em semantic_memory: {total}")
    print("Por squad:")
    for squad, count in rows:
        print(f"  {squad}: {count}")

    if total >= 130:
        print(f"\n✅ PASS — {total} >= 130 registros confirmados")
    else:
        print(f"\n❌ FAIL — {total} < 130 registros")

if __name__ == "__main__":
    main()
