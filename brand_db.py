#!/usr/bin/env python3
"""
Brand DB — banco de dados para 5000+ marcas/perfis
SQLite async com aiosqlite. Suporta CRUD, status por plataforma, fila de jobs.
"""
import os
import json
import asyncio
import aiosqlite
from datetime import datetime
from typing import Optional, List, Dict, Any

DB_PATH = os.path.join(os.path.dirname(__file__), "social_sessions", "brands.db")

PLATFORMS = ["instagram", "tiktok", "youtube", "twitter", "linkedin", "facebook"]

# Status de cada ação por plataforma
STATUS = {
    "pending":    "aguardando",
    "creating":   "criando_perfil",
    "active":     "perfil_ativo",
    "posting":    "postando",
    "error":      "erro",
    "done":       "concluido",
}

async def init_db():
    """Cria as tabelas se não existirem."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS brands (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                niche       TEXT NOT NULL,
                audience    TEXT NOT NULL,
                bio         TEXT,
                tone        TEXT,
                personality TEXT,
                content_strategy TEXT,
                visual_style TEXT,
                created_at  TEXT DEFAULT (datetime('now')),
                updated_at  TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS platform_profiles (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                brand_id    INTEGER NOT NULL,
                platform    TEXT NOT NULL,
                username    TEXT,
                profile_url TEXT,
                session_file TEXT,
                status      TEXT DEFAULT 'pending',
                error_msg   TEXT,
                created_at  TEXT DEFAULT (datetime('now')),
                updated_at  TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (brand_id) REFERENCES brands(id),
                UNIQUE(brand_id, platform)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS content_queue (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                brand_id    INTEGER NOT NULL,
                platform    TEXT NOT NULL,
                content_type TEXT NOT NULL,
                roteiro     TEXT,
                legenda     TEXT,
                hashtags    TEXT,
                media_path  TEXT,
                status      TEXT DEFAULT 'pending',
                scheduled_at TEXT,
                posted_at   TEXT,
                error_msg   TEXT,
                created_at  TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (brand_id) REFERENCES brands(id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                job_type    TEXT NOT NULL,
                brand_id    INTEGER,
                payload     TEXT,
                status      TEXT DEFAULT 'pending',
                worker_id   TEXT,
                started_at  TEXT,
                finished_at TEXT,
                result      TEXT,
                error_msg   TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            )
        """)
        # Índices para performance em 5000+ registros
        await db.execute("CREATE INDEX IF NOT EXISTS idx_brands_niche ON brands(niche)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_platform_status ON platform_profiles(status)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_queue_status ON content_queue(status, platform)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, job_type)")
        await db.commit()

async def insert_brand(name: str, niche: str, audience: str,
                       bio: str = "", tone: str = "", personality: str = "",
                       content_strategy: str = "", visual_style: str = "") -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO brands (name, niche, audience, bio, tone, personality, content_strategy, visual_style)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, niche, audience, bio, tone, personality, content_strategy, visual_style))
        await db.commit()
        brand_id = cursor.lastrowid
        # Cria registro pending para cada plataforma
        for platform in PLATFORMS:
            await db.execute("""
                INSERT OR IGNORE INTO platform_profiles (brand_id, platform, status)
                VALUES (?, ?, 'pending')
            """, (brand_id, platform))
        await db.commit()
        return brand_id

async def insert_brands_batch(brands: List[Dict]) -> List[int]:
    """Insere múltiplas marcas de uma vez. Otimizado para 5000+."""
    ids = []
    async with aiosqlite.connect(DB_PATH) as db:
        for b in brands:
            cursor = await db.execute("""
                INSERT INTO brands (name, niche, audience, bio, tone, personality, content_strategy, visual_style)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (b.get("name",""), b.get("niche",""), b.get("audience",""),
                  b.get("bio",""), b.get("tone",""), b.get("personality",""),
                  b.get("content_strategy",""), b.get("visual_style","")))
            brand_id = cursor.lastrowid
            ids.append(brand_id)
            for platform in PLATFORMS:
                await db.execute("""
                    INSERT OR IGNORE INTO platform_profiles (brand_id, platform, status)
                    VALUES (?, ?, 'pending')
                """, (brand_id, platform))
        await db.commit()
    return ids

async def get_brand(brand_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM brands WHERE id=?", (brand_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

async def get_brands_by_status(platform: str, status: str, limit: int = 50) -> List[Dict]:
    """Busca marcas por status em uma plataforma. Para filas de worker."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT b.*, pp.status as platform_status, pp.username, pp.session_file
            FROM brands b
            JOIN platform_profiles pp ON b.id = pp.brand_id
            WHERE pp.platform=? AND pp.status=?
            LIMIT ?
        """, (platform, status, limit)) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

async def update_platform_status(brand_id: int, platform: str, status: str,
                                  username: str = None, session_file: str = None,
                                  error_msg: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE platform_profiles
            SET status=?, username=?, session_file=?, error_msg=?, updated_at=datetime('now')
            WHERE brand_id=? AND platform=?
        """, (status, username, session_file, error_msg, brand_id, platform))
        await db.commit()

async def enqueue_content(brand_id: int, platform: str, content_type: str,
                           roteiro: str, legenda: str, hashtags: str,
                           scheduled_at: str = None) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO content_queue (brand_id, platform, content_type, roteiro, legenda, hashtags, scheduled_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (brand_id, platform, content_type, roteiro, legenda, hashtags, scheduled_at))
        await db.commit()
        return cursor.lastrowid

async def get_pending_content(platform: str, limit: int = 10) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT cq.*, b.name as brand_name, b.niche, b.tone
            FROM content_queue cq
            JOIN brands b ON cq.brand_id = b.id
            WHERE cq.platform=? AND cq.status='pending'
            ORDER BY cq.scheduled_at ASC, cq.created_at ASC
            LIMIT ?
        """, (platform, limit)) as cur:
            return [dict(r) for r in await cur.fetchall()]

async def get_stats() -> Dict:
    """Retorna estatísticas gerais do sistema."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM brands") as cur:
            total_brands = (await cur.fetchone())[0]
        stats = {"total_brands": total_brands, "platforms": {}}
        for platform in PLATFORMS:
            async with db.execute("""
                SELECT status, COUNT(*) as cnt
                FROM platform_profiles WHERE platform=?
                GROUP BY status
            """, (platform,)) as cur:
                rows = await cur.fetchall()
                stats["platforms"][platform] = {r[0]: r[1] for r in rows}
        async with db.execute("SELECT COUNT(*) FROM content_queue WHERE status='pending'") as cur:
            stats["content_pending"] = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM content_queue WHERE status='posted'") as cur:
            stats["content_posted"] = (await cur.fetchone())[0]
        return stats
