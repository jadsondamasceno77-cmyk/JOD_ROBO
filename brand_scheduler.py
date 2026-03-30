#!/usr/bin/env python3
"""
Brand Scheduler — processa 1 marca por vez, sequencialmente, durante 20 dias.
Cada marca passa por: identidade → criação de perfis → conteúdo → agendamento.
Nunca processa duas marcas ao mesmo tempo.
"""
import os
import json
import asyncio
import logging
import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from brand_db import (
    DB_PATH, init_db, get_brand, update_platform_status,
    enqueue_content, get_stats, PLATFORMS
)
from brand_pipeline import (
    generate_brand_identity, generate_content_pack, _llm
)

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s")
log = logging.getLogger("BrandScheduler")

# ─── Estado do Scheduler ──────────────────────────────────────────────────────
_scheduler: Optional[AsyncIOScheduler] = None
_lock = asyncio.Lock()          # garante 1 marca por vez
_current_brand_id: Optional[int] = None
_running = False

# ─── Fila de Marcas a Processar ──────────────────────────────────────────────

async def enqueue_brand(niche: str, audience: str, extra: dict = {}) -> int:
    """Adiciona uma marca à fila de processamento."""
    await init_db()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO brands (name, niche, audience)
            VALUES (?, ?, ?)
        """, (f"pending_{niche[:20]}", niche, audience))
        brand_id = cursor.lastrowid
        for platform in PLATFORMS:
            await db.execute("""
                INSERT OR IGNORE INTO platform_profiles (brand_id, platform, status)
                VALUES (?, ?, 'pending')
            """, (brand_id, platform))
        # Registra job na fila
        await db.execute("""
            INSERT INTO jobs (job_type, brand_id, payload, status)
            VALUES ('full_setup', ?, ?, 'pending')
        """, (brand_id, json.dumps({"niche": niche, "audience": audience, **extra})))
        await db.commit()
        log.info(f"[queue] brand_id={brand_id} nicho={niche} adicionado à fila")
        return brand_id

async def get_next_pending_job() -> Optional[Dict]:
    """Pega o próximo job pendente da fila (ordem de chegada)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT j.*, b.niche, b.audience
            FROM jobs j
            JOIN brands b ON j.brand_id = b.id
            WHERE j.status = 'pending' AND j.job_type = 'full_setup'
            ORDER BY j.created_at ASC
            LIMIT 1
        """) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

async def mark_job(job_id: int, status: str, result: str = "", error: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.now().isoformat()
        if status == "running":
            await db.execute("UPDATE jobs SET status=?, started_at=? WHERE id=?",
                             (status, now, job_id))
        else:
            await db.execute("UPDATE jobs SET status=?, finished_at=?, result=?, error_msg=? WHERE id=?",
                             (status, now, result, error, job_id))
        await db.commit()

# ─── Processamento Completo de Uma Marca ────────────────────────────────────

async def process_brand_full(brand_id: int, job_id: int):
    """
    Fluxo completo de uma marca:
    1. Gera identidade (nome, bio, tom, estratégia)
    2. Salva identidade no banco
    3. Gera conteúdo para cada plataforma (1 pack por plataforma)
    4. Agenda os posts com intervalo entre plataformas
    """
    global _current_brand_id
    _current_brand_id = brand_id

    log.info(f"[process] INÍCIO brand_id={brand_id}")
    await mark_job(job_id, "running")

    brand = await get_brand(brand_id)
    if not brand:
        await mark_job(job_id, "error", error="brand não encontrado")
        return

    try:
        # ── Passo 1: Gerar Identidade ──────────────────────────────────
        log.info(f"[process] brand_id={brand_id} → gerando identidade...")
        identity = await generate_brand_identity(brand["niche"], brand["audience"], brand_id)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                UPDATE brands SET name=?, bio=?, tone=?, personality=?,
                content_strategy=?, visual_style=?, updated_at=datetime('now')
                WHERE id=?
            """, (
                identity.name, identity.bio, identity.tone, identity.personality,
                f"{identity.content_strategy} | Pilares: {', '.join(identity.content_pillars)}",
                identity.visual_style, brand_id
            ))
            await db.commit()

        log.info(f"[process] brand_id={brand_id} nome='{identity.name}' ✓ identidade gerada")
        brand = await get_brand(brand_id)  # recarrega com dados atualizados

        # ── Passo 2: Gerar Conteúdo por Plataforma ────────────────────
        content_types = {
            "instagram": "reels",
            "tiktok":    "reels",
            "youtube":   "video",
            "twitter":   "post",
            "linkedin":  "post",
            "facebook":  "post",
        }

        for i, platform in enumerate(PLATFORMS):
            log.info(f"[process] brand_id={brand_id} → gerando conteúdo para {platform}...")
            try:
                ctype = content_types[platform]
                pack = await generate_content_pack(brand, platform, ctype)

                # Agenda com espaçamento de 4h entre plataformas
                scheduled = (datetime.now() + timedelta(hours=i * 4)).isoformat()

                await enqueue_content(
                    brand_id, platform, ctype,
                    roteiro=pack.roteiro,
                    legenda=pack.legenda,
                    hashtags=pack.hashtags,
                    scheduled_at=scheduled
                )
                await update_platform_status(brand_id, platform, "active")
                log.info(f"[process] brand_id={brand_id} platform={platform} ✓")
                await asyncio.sleep(1)  # pausa entre plataformas

            except Exception as e:
                log.error(f"[process] brand_id={brand_id} platform={platform} erro={e}")
                await update_platform_status(brand_id, platform, "error", error_msg=str(e))

        # ── Passo 3: Gera Calendário Editorial (30 dias) ──────────────
        log.info(f"[process] brand_id={brand_id} → gerando calendário...")
        try:
            llm = _llm()
            calendar = await asyncio.get_event_loop().run_in_executor(None, llm.invoke,
                f"""Crie calendário editorial de 30 dias para:
Marca: {brand['name']}
Nicho: {brand['niche']}
Público: {brand['audience']}
Tom: {brand.get('tone','')}

Formato: Dia N | Plataforma | Formato | Tema | Gancho
Liste 30 dias, 1 por linha."""
            )
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("""
                    INSERT INTO jobs (job_type, brand_id, payload, status)
                    VALUES ('calendar', ?, ?, 'done')
                """, (brand_id, calendar.content if hasattr(calendar, 'content') else str(calendar)))
                await db.commit()
            log.info(f"[process] brand_id={brand_id} ✓ calendário gerado")
        except Exception as e:
            log.warning(f"[process] brand_id={brand_id} calendário erro={e}")

        result = json.dumps({
            "nome": brand.get("name", ""),
            "nicho": brand["niche"],
            "plataformas_ativas": len([p for p in PLATFORMS]),
            "conteudo_na_fila": len(PLATFORMS)
        })
        await mark_job(job_id, "done", result=result)
        log.info(f"[process] CONCLUÍDO brand_id={brand_id} nome='{brand.get('name')}'")

    except Exception as e:
        log.error(f"[process] ERRO brand_id={brand_id}: {e}")
        await mark_job(job_id, "error", error=str(e))
    finally:
        _current_brand_id = None

# ─── Tick do Scheduler ───────────────────────────────────────────────────────

async def scheduler_tick():
    """
    Executado a cada intervalo configurado.
    Se não há marca sendo processada, pega a próxima da fila.
    Garante: 1 marca por vez, nunca paralelo.
    """
    global _running
    if _lock.locked():
        log.debug("[tick] scheduler ocupado — aguardando marca atual terminar")
        return

    async with _lock:
        job = await get_next_pending_job()
        if not job:
            log.debug("[tick] fila vazia — nada a processar")
            return

        brand_id = job["brand_id"]
        job_id   = job["id"]
        log.info(f"[tick] processando brand_id={brand_id} nicho={job['niche']}")
        _running = True
        await process_brand_full(brand_id, job_id)
        _running = False

# ─── Controle do Scheduler ───────────────────────────────────────────────────

def start_scheduler(interval_minutes: int = 30):
    """
    Inicia o scheduler.
    interval_minutes: quanto tempo espera entre marcas (padrão 30min).
    Para 5000 marcas em 20 dias: ~144 marcas/dia → a cada 10min.
    """
    global _scheduler
    if _scheduler and _scheduler.running:
        log.warning("[scheduler] já está rodando")
        return

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        scheduler_tick,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="brand_processor",
        name="Processa próxima marca da fila",
        replace_existing=True,
        max_instances=1,  # nunca duas instâncias ao mesmo tempo
    )
    _scheduler.start()
    log.info(f"[scheduler] iniciado — intervalo={interval_minutes}min")

def stop_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown()
        log.info("[scheduler] parado")

async def get_scheduler_status() -> Dict:
    """Status do scheduler e fila."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT status, COUNT(*) as cnt FROM jobs
            WHERE job_type='full_setup' GROUP BY status
        """) as cur:
            job_counts = {r["status"]: r["cnt"] for r in await cur.fetchall()}

        async with db.execute("""
            SELECT j.id, j.status, j.created_at, j.started_at, j.finished_at,
                   b.name, b.niche
            FROM jobs j JOIN brands b ON j.brand_id=b.id
            WHERE j.job_type='full_setup' AND j.status IN ('running','pending')
            ORDER BY j.created_at ASC LIMIT 5
        """) as cur:
            proximas = [dict(r) for r in await cur.fetchall()]

    return {
        "scheduler_ativo": _scheduler.running if _scheduler else False,
        "processando_agora": _current_brand_id,
        "jobs": job_counts,
        "proximas_marcas": proximas,
        "db_stats": await get_stats(),
    }
