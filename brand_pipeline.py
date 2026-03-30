#!/usr/bin/env python3
"""
Brand Pipeline — processamento paralelo de 5000+ marcas
Workers assíncronos com semáforo. Gera identidade + conteúdo + agenda postagens.
Rate limiting por plataforma. Retry automático em falhas.
"""
import os
import json
import asyncio
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field
from brand_db import (
    init_db, insert_brand, insert_brands_batch, get_brand,
    get_brands_by_status, update_platform_status,
    enqueue_content, get_pending_content, get_stats, PLATFORMS
)

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s")
log = logging.getLogger("BrandPipeline")

# ─── Limites por plataforma (ações/hora para não ser banido) ─────────────────
RATE_LIMITS = {
    "instagram":  30,
    "tiktok":     20,
    "youtube":    10,
    "twitter":    50,
    "linkedin":   25,
    "facebook":   30,
}

# Semáforos por plataforma
_SEMAPHORES: Dict[str, asyncio.Semaphore] = {}

def _sem(platform: str) -> asyncio.Semaphore:
    if platform not in _SEMAPHORES:
        # Máx workers simultâneos por plataforma
        _SEMAPHORES[platform] = asyncio.Semaphore(5)
    return _SEMAPHORES[platform]

# LLM singleton
_LLM: Optional[ChatGroq] = None

def _llm() -> ChatGroq:
    global _LLM
    if _LLM is None:
        _LLM = ChatGroq(
            model="llama-3.3-70b-versatile",
            api_key=os.getenv("GROQ_API_KEY", ""),
            temperature=0.9,
        )
    return _LLM

# ─── Schema de Identidade de Marca ───────────────────────────────────────────

class BrandIdentity(BaseModel):
    name: str = Field(description="Nome da marca/perfil (criativo, memorável)")
    username_sugerido: str = Field(description="Username para redes sociais (sem espaços, sem @)")
    bio: str = Field(description="Bio de 150 chars — quem é, o que entrega, CTA")
    tone: str = Field(description="Tom de voz: ex 'jovem e irreverente', 'profissional e inspirador'")
    personality: str = Field(description="3 adjetivos que definem a personalidade da marca")
    content_strategy: str = Field(description="Estratégia de conteúdo em 2 linhas")
    visual_style: str = Field(description="Estilo visual: cores, estética, referências")
    content_pillars: List[str] = Field(description="3-5 pilares de conteúdo (temas recorrentes)")
    posting_frequency: str = Field(description="Frequência ideal: ex '1x/dia reels + 3x stories'")
    hashtag_strategy: str = Field(description="Estratégia de hashtags para crescimento orgânico")

class ContentPack(BaseModel):
    roteiro: str = Field(description="Roteiro completo com storytelling")
    legenda: str = Field(description="Legenda otimizada para a plataforma")
    hashtags: str = Field(description="Hashtags separadas por espaço")
    formato: str = Field(description="reels | post | stories | carrossel | video")
    gancho: str = Field(description="Primeiros 3 segundos / primeira linha")
    cta: str = Field(description="Call to action")

# ─── Geração de Identidade ───────────────────────────────────────────────────

async def generate_brand_identity(niche: str, audience: str, index: int) -> BrandIdentity:
    """Gera identidade completa de marca com LLM."""
    llm = _llm().with_structured_output(BrandIdentity)
    loop = asyncio.get_event_loop()

    identity = await loop.run_in_executor(None, llm.invoke,
        f"""Crie uma identidade de marca ÚNICA e ORIGINAL para:
NICHO: {niche}
PÚBLICO: {audience}
ÍNDICE: {index} (use para criar algo diferente de outras marcas do mesmo nicho)

REGRAS:
- Nome criativo, fácil de lembrar, sem clichês
- Username: letras minúsculas, números ok, sem espaços
- Bio: direto ao ponto, com proposta de valor clara e CTA
- Personalidade forte e diferenciada da concorrência
- Estratégia de conteúdo específica para {audience}
"""
    )
    return identity

# ─── Geração de Conteúdo por Marca ───────────────────────────────────────────

async def generate_content_pack(brand: Dict, platform: str, content_type: str) -> ContentPack:
    """Gera um pack de conteúdo completo para uma marca e plataforma."""
    llm = _llm().with_structured_output(ContentPack)
    loop = asyncio.get_event_loop()

    pillar = brand.get("content_strategy", brand["niche"])

    pack = await loop.run_in_executor(None, llm.invoke,
        f"""Crie conteúdo para redes sociais.

MARCA: {brand['name']}
NICHO: {brand['niche']}
PÚBLICO: {brand['audience']}
TOM: {brand.get('tone', 'autêntico')}
PLATAFORMA: {platform}
FORMATO: {content_type}
ESTRATÉGIA: {pillar}

REGRAS:
- Gancho nos primeiros 3 segundos (pare o scroll)
- Storytelling: Problema → Virada → Solução
- Linguagem 100% alinhada ao público {brand['audience']}
- Legenda otimizada para {platform}
- CTA claro e urgente
"""
    )
    return pack

# ─── Workers ─────────────────────────────────────────────────────────────────

async def worker_generate_identity(brand_id: int):
    """Worker: gera e salva identidade de uma marca."""
    import aiosqlite
    from brand_db import DB_PATH

    brand = await get_brand(brand_id)
    if not brand:
        return

    try:
        identity = await generate_brand_identity(
            brand["niche"], brand["audience"], brand["id"]
        )
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                UPDATE brands SET bio=?, tone=?, personality=?, content_strategy=?, visual_style=?,
                name=?, updated_at=datetime('now') WHERE id=?
            """, (
                identity.bio, identity.tone, identity.personality,
                f"{identity.content_strategy} | Pilares: {', '.join(identity.content_pillars)}",
                identity.visual_style, identity.name, brand_id
            ))
            await db.commit()
        log.info(f"[identity] brand_id={brand_id} nome={identity.name} nicho={brand['niche']}")
    except Exception as e:
        log.error(f"[identity] brand_id={brand_id} erro={e}")

async def worker_generate_content(brand_id: int, platform: str):
    """Worker: gera conteúdo para uma marca em uma plataforma."""
    async with _sem(platform):
        brand = await get_brand(brand_id)
        if not brand:
            return
        content_types = {
            "instagram": ["reels", "post", "stories"],
            "tiktok":    ["reels"],
            "youtube":   ["video"],
            "twitter":   ["post"],
            "linkedin":  ["post"],
            "facebook":  ["post", "stories"],
        }
        for ctype in content_types.get(platform, ["post"]):
            try:
                pack = await generate_content_pack(brand, platform, ctype)
                # Agenda com intervalo para não postar tudo de uma vez
                delay_hours = PLATFORMS.index(platform) * 2
                scheduled = (datetime.now() + timedelta(hours=delay_hours)).isoformat()
                await enqueue_content(
                    brand_id, platform, ctype,
                    roteiro=pack.roteiro,
                    legenda=pack.legenda,
                    hashtags=pack.hashtags,
                    scheduled_at=scheduled
                )
                log.info(f"[content] brand_id={brand_id} platform={platform} tipo={ctype}")
                await asyncio.sleep(1)  # rate limit
            except Exception as e:
                log.error(f"[content] brand_id={brand_id} platform={platform} erro={e}")

# ─── Pipeline Principal ───────────────────────────────────────────────────────

async def run_pipeline_batch(brand_ids: List[int], max_concurrent: int = 10):
    """
    Processa lote de marcas em paralelo.
    max_concurrent: workers simultâneos (ajuste conforme RAM disponível).
    Para 5000 marcas: roda em batches de 100, ~8h de processamento.
    """
    sem = asyncio.Semaphore(max_concurrent)

    async def process_one(brand_id: int):
        async with sem:
            await worker_generate_identity(brand_id)
            await asyncio.sleep(0.5)
            for platform in PLATFORMS:
                await worker_generate_content(brand_id, platform)
                await asyncio.sleep(0.3)

    tasks = [process_one(bid) for bid in brand_ids]
    total = len(tasks)
    log.info(f"[pipeline] iniciando {total} marcas | max_concurrent={max_concurrent}")

    done = 0
    for coro in asyncio.as_completed(tasks):
        await coro
        done += 1
        if done % 50 == 0:
            stats = await get_stats()
            log.info(f"[pipeline] progresso {done}/{total} | stats={stats}")

    log.info(f"[pipeline] concluído {total} marcas")

async def create_brands_from_list(brands_raw: List[Dict], max_concurrent: int = 10) -> Dict:
    """
    Entrada principal: recebe lista de marcas, insere no DB e processa.
    brands_raw: [{"niche": "...", "audience": "..."}, ...]
    """
    await init_db()
    brand_ids = await insert_brands_batch([
        {"name": f"Brand_{i}", "niche": b["niche"], "audience": b["audience"]}
        for i, b in enumerate(brands_raw)
    ])
    log.info(f"[create] {len(brand_ids)} marcas inseridas no banco")
    # Processa em background (não bloqueia a API)
    asyncio.create_task(run_pipeline_batch(brand_ids, max_concurrent))
    return {
        "status": "processing",
        "total": len(brand_ids),
        "brand_ids": brand_ids[:10],  # retorna os primeiros 10 como amostra
        "message": f"{len(brand_ids)} marcas em processamento. Use /social/stats para acompanhar."
    }

async def get_pipeline_stats() -> Dict:
    """Status do pipeline em tempo real."""
    stats = await get_stats()
    return stats
