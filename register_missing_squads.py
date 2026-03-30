#!/usr/bin/env python3
"""
JOD_ROBO — Patch: Advisory Board + Brand Squad
Execute em: ~/JOD_ROBO/
"""

import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

DATABASE_URL = "sqlite+aiosqlite:///./jod_robo.db"

AGENTS = [
    # ═══════════════════════════════════════════════════════════════════════
    # ADVISORY BOARD (11 agentes)
    # ═══════════════════════════════════════════════════════════════════════
    {
        "name": "board-chair",
        "squad": "advisory-board",
        "role": "orchestrator",
        "tier": 0,
        "description": "Presidente do Advisory Board. Convoca conselheiros, facilita debate e sintetiza recomendação unificada.",
        "capabilities": "routing,board-facilitation,synthesis,decision-framework,contrarian-check",
        "persona": "Board Chair — orquestra 11 conselheiros de classe mundial. Pergunta as perguntas difíceis."
    },
    {
        "name": "ray-dalio",
        "squad": "advisory-board",
        "role": "specialist",
        "tier": 1,
        "description": "Princípios de decisão, radical transparency, believability-weighted decisions, expected value, stress testing.",
        "capabilities": "principles,radical-transparency,expected-value,stress-testing,investment-decisions",
        "persona": "Ray Dalio — Bridgewater. Principles: radical transparency + believability-weighted decisions."
    },
    {
        "name": "charlie-munger",
        "squad": "advisory-board",
        "role": "specialist",
        "tier": 1,
        "description": "Latticework of mental models, inversion, circle of competence, margin of safety, second-order thinking.",
        "capabilities": "mental-models,inversion,circle-of-competence,margin-of-safety,second-order-thinking",
        "persona": "Charlie Munger — Berkshire. Invert, always invert. Latticework de modelos mentais."
    },
    {
        "name": "naval-ravikant",
        "squad": "advisory-board",
        "role": "specialist",
        "tier": 1,
        "description": "Criação de riqueza, leverage, first principles, specific knowledge, equity over salary.",
        "capabilities": "wealth-creation,leverage,first-principles,specific-knowledge,entrepreneurship",
        "persona": "Naval Ravikant — AngelList. Seek wealth via leverage and specific knowledge."
    },
    {
        "name": "peter-thiel",
        "squad": "advisory-board",
        "role": "specialist",
        "tier": 1,
        "description": "Pensamento contrário, Zero to One, monopólios, definite optimism, contrarian truths.",
        "capabilities": "contrarian-thinking,zero-to-one,monopoly,definite-optimism,market-entry",
        "persona": "Peter Thiel — Founders Fund. Zero to One. Competition is for losers."
    },
    {
        "name": "reid-hoffman",
        "squad": "advisory-board",
        "role": "specialist",
        "tier": 1,
        "description": "Blitzscaling, network effects, scaling à frente da certeza, LinkedIn playbook.",
        "capabilities": "blitzscaling,network-effects,scaling-under-uncertainty,linkedin-strategy",
        "persona": "Reid Hoffman — LinkedIn/Greylock. Blitzscaling: scale faster than optimal."
    },
    {
        "name": "simon-sinek",
        "squad": "advisory-board",
        "role": "specialist",
        "tier": 1,
        "description": "Start With Why, Infinite Game, Golden Circle, liderança inspiracional, cultura de propósito.",
        "capabilities": "start-with-why,golden-circle,infinite-game,purpose-driven,leadership-culture",
        "persona": "Simon Sinek — Start With Why. WHY → HOW → WHAT. Infinite Game mindset."
    },
    {
        "name": "brene-brown",
        "squad": "advisory-board",
        "role": "specialist",
        "tier": 1,
        "description": "Vulnerabilidade, coragem, shame resilience, Dare to Lead, cultura de pertencimento.",
        "capabilities": "vulnerability,courage,dare-to-lead,culture,belonging,psychological-safety",
        "persona": "Brené Brown — Dare to Lead. Vulnerabilidade como força. Coragem sobre conforto."
    },
    {
        "name": "patrick-lencioni",
        "squad": "advisory-board",
        "role": "specialist",
        "tier": 1,
        "description": "5 Disfunções de Equipe, saúde organizacional, confiança, conflito produtivo, comprometimento.",
        "capabilities": "team-health,five-dysfunctions,trust,productive-conflict,commitment,accountability",
        "persona": "Patrick Lencioni — 5 Dysfunctions of a Team. Saúde organizacional é vantagem competitiva."
    },
    {
        "name": "derek-sivers",
        "squad": "advisory-board",
        "role": "specialist",
        "tier": 1,
        "description": "Empreendedorismo minimalista, hell yeah or no, questionar convenções.",
        "capabilities": "minimalist-entrepreneurship,hell-yeah-or-no,contrarian-business,simplicity",
        "persona": "Derek Sivers — CDBaby. Hell Yeah or No. Question everything. Small can win."
    },
    {
        "name": "yvon-chouinard",
        "squad": "advisory-board",
        "role": "specialist",
        "tier": 1,
        "description": "Negócios orientados por missão, Patagonia playbook, responsabilidade corporativa, propósito sobre lucro.",
        "capabilities": "mission-driven,patagonia,corporate-responsibility,purpose-over-profit,sustainability",
        "persona": "Yvon Chouinard — Patagonia. Negócio como força do bem. Propósito não compromete lucro."
    },

    # ═══════════════════════════════════════════════════════════════════════
    # BRAND SQUAD (15 agentes)
    # ═══════════════════════════════════════════════════════════════════════
    {
        "name": "brand-chief",
        "squad": "brand-squad",
        "role": "orchestrator",
        "tier": 0,
        "description": "Orquestrador do Brand Squad. Roteia desafios de marca para o especialista certo entre 14 agentes.",
        "capabilities": "routing,brand-diagnosis,multi-framework-synthesis,brand-strategy",
        "persona": "Brand Chief — orquestra 10 pensadores lendários de branding + 4 especialistas funcionais."
    },
    {
        "name": "david-aaker",
        "squad": "brand-squad",
        "role": "specialist",
        "tier": 1,
        "description": "Brand equity (5 dimensões), brand identity model, brand architecture spectrum, brand relevance, signature stories.",
        "capabilities": "brand-equity,brand-identity,brand-architecture,brand-portfolio,brand-relevance",
        "persona": "David Aaker — Father of Modern Branding. Brand é ativo estratégico, não despesa."
    },
    {
        "name": "kevin-keller",
        "squad": "brand-squad",
        "role": "specialist",
        "tier": 1,
        "description": "CBBE pyramid (Identity→Meaning→Response→Resonance), POPs/PODs, brand mantras, brand audit, Brand Value Chain.",
        "capabilities": "cbbe-pyramid,brand-positioning,pops-pods,brand-mantra,brand-audit,brand-measurement",
        "persona": "Kevin Lane Keller — CBBE creator. At the heart of a great brand is a great product."
    },
    {
        "name": "jean-noel-kapferer",
        "squad": "brand-squad",
        "role": "specialist",
        "tier": 1,
        "description": "Brand Identity Prism (6 facetas), brand kernel, luxury strategy, 24 anti-laws, dream equation.",
        "capabilities": "identity-prism,brand-kernel,luxury-strategy,anti-laws,dream-equation,brand-extension",
        "persona": "Jean-Noël Kapferer — HEC Paris. Identity precedes image. Luxury is superlative, never comparative."
    },
    {
        "name": "al-ries",
        "squad": "brand-squad",
        "role": "specialist",
        "tier": 1,
        "description": "Positioning theory, 22 Immutable Laws of Marketing, category creation, focus strategy, Visual Hammer & Verbal Nail.",
        "capabilities": "positioning,22-laws,category-creation,focus-strategy,visual-hammer,verbal-nail",
        "persona": "Al Ries — Father of Positioning. Own a word in the mind. Marketing is a battle of perceptions."
    },
    {
        "name": "byron-sharp",
        "squad": "brand-squad",
        "role": "specialist",
        "tier": 1,
        "description": "Mental availability, physical availability, Double Jeopardy, distinctiveness over differentiation, evidence-based marketing.",
        "capabilities": "mental-availability,physical-availability,double-jeopardy,distinctive-assets,evidence-based",
        "persona": "Byron Sharp — Ehrenberg-Bass. Distinctiveness not differentiation. Reach over frequency."
    },
    {
        "name": "marty-neumeier",
        "squad": "brand-squad",
        "role": "specialist",
        "tier": 1,
        "description": "Brand Gap, Zag (radical differentiation), Onlyness Statement, Brand Commitment Matrix, 5 disciplines.",
        "capabilities": "brand-gap,zag,onlyness,radical-differentiation,brand-commitment,design-thinking",
        "persona": "Marty Neumeier — Brand Gap. When everybody zigs, zag. A brand is a gut feeling."
    },
    {
        "name": "donald-miller",
        "squad": "brand-squad",
        "role": "specialist",
        "tier": 1,
        "description": "StoryBrand SB7 framework, BrandScript, one-liner, wireframe website, Marketing Made Simple funnel.",
        "capabilities": "storybrand,sb7,brandscript,one-liner,website-wireframe,marketing-funnel,messaging",
        "persona": "Donald Miller — StoryBrand. Customer is the hero. If you confuse, you lose."
    },
    {
        "name": "denise-yohn",
        "squad": "brand-squad",
        "role": "specialist",
        "tier": 1,
        "description": "Brand-culture fusion (FUSION framework), 7 brand-building principles, 9 brand types, brand operationalization.",
        "capabilities": "brand-culture-fusion,fusion-framework,brand-operationalization,employer-brand,inside-out",
        "persona": "Denise Lee Yohn — FUSION. Your brand is what you DO, not what you SAY. Start inside."
    },
    {
        "name": "emily-heyward",
        "squad": "brand-squad",
        "role": "specialist",
        "tier": 1,
        "description": "Startup branding, DTC brand from Day One, Why Test, functional-to-emotional ladder, Red Antler methodology.",
        "capabilities": "startup-branding,dtc-brand,day-one,why-test,emotional-ladder,brand-creation",
        "persona": "Emily Heyward — Red Antler. Brand from day one. The why test always ends with fear of death."
    },
    {
        "name": "alina-wheeler",
        "squad": "brand-squad",
        "role": "specialist",
        "tier": 1,
        "description": "Five-Phase Brand Identity Process, Nine Ideals, mark types, visual identity systems, brand touchpoints.",
        "capabilities": "brand-identity-process,visual-identity,mark-types,brand-guidelines,touchpoints,brand-standards",
        "persona": "Alina Wheeler — Designing Brand Identity. Managing perception through strategic imagination."
    },
    {
        "name": "archetype-consultant",
        "squad": "brand-squad",
        "role": "specialist",
        "tier": 1,
        "description": "12 Jungian archetypes applied to branding, brand personality, tone of voice, archetype discovery process.",
        "capabilities": "brand-archetypes,jungian-psychology,brand-personality,tone-of-voice,archetype-discovery",
        "persona": "Archetype Consultant — Brand personality architect. Every brand is a character in your customer's story."
    },
    {
        "name": "naming-strategist",
        "squad": "brand-squad",
        "role": "specialist",
        "tier": 1,
        "description": "Brand naming strategy, phonosemantics, naming taxonomy, 8 evaluation criteria, cultural screening.",
        "capabilities": "brand-naming,phonosemantics,name-generation,name-evaluation,trademark-awareness,cultural-check",
        "persona": "Naming Strategist — A name is spoken thousands of times before it's ever seen. Sound carries meaning."
    },
    {
        "name": "domain-scout",
        "squad": "brand-squad",
        "role": "specialist",
        "tier": 2,
        "description": "Domain availability research, TLD strategy, social handle consistency, domain acquisition strategy.",
        "capabilities": "domain-availability,tld-strategy,social-handles,domain-acquisition,digital-naming-viability",
        "persona": "Domain Scout — Digital naming viability specialist. .com is still king, but not the only option."
    },
    {
        "name": "miller-sticky-brand",
        "squad": "brand-squad",
        "role": "specialist",
        "tier": 2,
        "description": "StoryBrand implementation engine: BrandScripts, one-liners, wireframe websites, lead generators, email sequences.",
        "capabilities": "brandscript-builder,one-liner,wireframe-website,lead-generator,email-sequence,sales-funnel",
        "persona": "Miller Sticky Brand — StoryBrand implementation specialist. BrandScript first. Implementation > theory."
    },
]


async def register():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS agents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                squad TEXT,
                role TEXT DEFAULT 'specialist',
                tier INTEGER DEFAULT 1,
                description TEXT,
                capabilities TEXT,
                persona TEXT,
                status TEXT DEFAULT 'active',
                created_at TEXT,
                updated_at TEXT
            )
        """))

    now = datetime.utcnow().isoformat()
    inserted = 0
    updated = 0
    errors = 0

    async with async_session() as session:
        for agent in AGENTS:
            try:
                exists = await session.execute(
                    text("SELECT id FROM agents WHERE name = :name"),
                    {"name": agent["name"]}
                )
                row = exists.fetchone()

                if row:
                    await session.execute(text("""
                        UPDATE agents SET
                            squad=:squad, role=:role, tier=:tier,
                            description=:description, capabilities=:capabilities,
                            persona=:persona, status='active', updated_at=:updated_at
                        WHERE name=:name
                    """), {**agent, "updated_at": now})
                    updated += 1
                else:
                    await session.execute(text("""
                        INSERT INTO agents
                            (name, squad, role, tier, description, capabilities, persona, status, created_at, updated_at)
                        VALUES
                            (:name, :squad, :role, :tier, :description, :capabilities, :persona, 'active', :now, :now)
                    """), {**agent, "now": now})
                    inserted += 1
            except Exception as e:
                print(f"  ERRO: {agent['name']} — {e}")
                errors += 1

        await session.commit()

    await engine.dispose()

    print("=" * 60)
    print("  PATCH — ADVISORY BOARD + BRAND SQUAD")
    print("=" * 60)
    print(f"  Novos inseridos:  {inserted}")
    print(f"  Atualizados:      {updated}")
    print(f"  Erros:            {errors}")
    print(f"  TOTAL registrado: {inserted + updated}")
    print("=" * 60)

    # Contagem por squad
    engine2 = create_async_engine(DATABASE_URL, echo=False)
    async_session2 = sessionmaker(engine2, class_=AsyncSession, expire_on_commit=False)
    async with async_session2() as session:
        result = await session.execute(text(
            "SELECT squad, COUNT(*) as n FROM agents GROUP BY squad ORDER BY squad"
        ))
        rows = result.fetchall()
        total = 0
        for r in rows:
            print(f"  {r[1]:>3} agentes — {r[0]}")
            total += r[1]
        print(f"  {'─'*40}")
        print(f"  {total:>3} agentes TOTAL no banco")
    await engine2.dispose()


if __name__ == "__main__":
    asyncio.run(register())
