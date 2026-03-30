#!/usr/bin/env python3
"""
Instagram Worker — engajamento automático via instagrapi
Follow / Like / Comment / DM / Share — 1 perfil por worker
"""
import os
import json
import asyncio
import random
import logging
from pathlib import Path
from datetime import datetime, time
from typing import Optional

import httpx
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, RateLimitError, BadPassword

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s")
log = logging.getLogger("instagram_worker")

# ─── Config ───────────────────────────────────────────────────────────────────

SESSIONS_DIR = Path("/app/sessions/instagram")
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

ELI_URL   = os.getenv("ELI_URL", "http://localhost:37779")
TOKEN     = os.getenv("JOD_TRUST_MANIFEST", "jod_robo_trust_2026_secure")
NICHE     = os.getenv("NICHE", "geral")
COUNTRY   = os.getenv("COUNTRY", "BR")
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "10"))

# Limites diários seguros por conta
DAILY_LIMITS = {
    "follows":    150,
    "likes":      300,
    "comments":   80,
    "dms":        50,
    "shares":     50,
}

# Hashtags por nicho
NICHE_HASHTAGS = {
    "fitness":         ["fitness","academia","treino","musculacao","gym"],
    "yoga":            ["yoga","meditacao","mindfulness","namaste","zenlife"],
    "nutricao":        ["nutricao","alimentacaosaudavel","dieta","saude"],
    "personal_branding": ["personalbranding","marca","reputacao","fundador"],
    "marketing_digital": ["marketingdigital","marketing","trafegopago","seo"],
    "design_grafico":  ["design","designgrafico","branding","identidadevisual"],
    "empreendedorismo":["empreendedorismo","startup","negocio","empresario"],
    "tecnologia":      ["tech","tecnologia","ia","inteligenciaartificial"],
    "geral":           ["brasil","empreendedor","negocio","marketing","design"],
}

AI_COMMENTS = [
    "Conteúdo incrível! Sempre aprendo muito aqui 🔥",
    "Que perspectiva poderosa! Salvei para rever depois.",
    "Isso faz todo sentido! Obrigado por compartilhar.",
    "Exatamente o que eu precisava ver hoje!",
    "Seu conteúdo é sempre muito valioso. Parabéns!",
    "Concordo totalmente! Muito bem explicado.",
    "Isso mudou minha visão sobre o assunto.",
    "Incrível demais! Já estou aplicando isso.",
    "Que conteúdo rico! Obrigado por isso.",
    "Sempre entregando valor real. Top demais!",
]

# ─── Worker ───────────────────────────────────────────────────────────────────

class InstagramWorker:
    def __init__(self, account: dict):
        self.username   = account["username"]
        self.password   = account["password"]
        self.brand_id   = account.get("brand_id", 0)
        self.session_path = SESSIONS_DIR / f"{self.username}.json"
        self.cl         = Client()
        self.daily_count = {k: 0 for k in DAILY_LIMITS}
        self._logged_in = False

    def _login(self) -> bool:
        try:
            if self.session_path.exists():
                self.cl.load_settings(str(self.session_path))
                self.cl.login(self.username, self.password)
                log.info(f"[{self.username}] Sessão restaurada")
            else:
                self.cl.login(self.username, self.password)
                self.cl.dump_settings(str(self.session_path))
                log.info(f"[{self.username}] Login novo OK")
            self._logged_in = True
            return True
        except BadPassword:
            log.error(f"[{self.username}] Senha incorreta")
            return False
        except Exception as e:
            log.error(f"[{self.username}] Login falhou: {e}")
            return False

    def _within_limit(self, action: str) -> bool:
        return self.daily_count.get(action, 0) < DAILY_LIMITS.get(action, 0)

    def _count(self, action: str):
        self.daily_count[action] = self.daily_count.get(action, 0) + 1

    async def _human_delay(self, min_s=2, max_s=8):
        await asyncio.sleep(random.uniform(min_s, max_s))

    def _get_hashtags(self) -> list:
        return NICHE_HASHTAGS.get(NICHE, NICHE_HASHTAGS["geral"])

    # ── Ações ────────────────────────────────────────────────────────────────

    async def follow_by_hashtag(self, hashtag: str, limit: int = 20):
        if not self._within_limit("follows"):
            return
        try:
            loop = asyncio.get_event_loop()
            medias = await loop.run_in_executor(
                None, lambda: self.cl.hashtag_medias_recent(hashtag, amount=limit)
            )
            for media in medias:
                if not self._within_limit("follows"):
                    break
                try:
                    await loop.run_in_executor(
                        None, lambda: self.cl.user_follow(media.user.pk)
                    )
                    self._count("follows")
                    log.info(f"[{self.username}] Seguiu @{media.user.username}")
                    await self._human_delay(3, 10)
                except Exception:
                    pass
        except Exception as e:
            log.warning(f"[{self.username}] follow_by_hashtag erro: {e}")

    async def like_by_hashtag(self, hashtag: str, limit: int = 30):
        if not self._within_limit("likes"):
            return
        try:
            loop = asyncio.get_event_loop()
            medias = await loop.run_in_executor(
                None, lambda: self.cl.hashtag_medias_recent(hashtag, amount=limit)
            )
            for media in medias:
                if not self._within_limit("likes"):
                    break
                try:
                    await loop.run_in_executor(
                        None, lambda: self.cl.media_like(media.id)
                    )
                    self._count("likes")
                    log.info(f"[{self.username}] Curtiu {media.id}")
                    await self._human_delay(2, 6)
                except Exception:
                    pass
        except Exception as e:
            log.warning(f"[{self.username}] like_by_hashtag erro: {e}")

    async def comment_by_hashtag(self, hashtag: str, limit: int = 10):
        if not self._within_limit("comments"):
            return
        try:
            loop = asyncio.get_event_loop()
            medias = await loop.run_in_executor(
                None, lambda: self.cl.hashtag_medias_recent(hashtag, amount=limit)
            )
            for media in medias:
                if not self._within_limit("comments"):
                    break
                try:
                    comment_text = random.choice(AI_COMMENTS)
                    await loop.run_in_executor(
                        None, lambda: self.cl.media_comment(media.id, comment_text)
                    )
                    self._count("comments")
                    log.info(f"[{self.username}] Comentou em {media.id}")
                    await self._human_delay(10, 30)
                except Exception:
                    pass
        except Exception as e:
            log.warning(f"[{self.username}] comment_by_hashtag erro: {e}")

    async def dm_followers_of(self, target_username: str, message: str, limit: int = 10):
        if not self._within_limit("dms"):
            return
        try:
            loop = asyncio.get_event_loop()
            user_id = await loop.run_in_executor(
                None, lambda: self.cl.user_id_from_username(target_username)
            )
            followers = await loop.run_in_executor(
                None, lambda: self.cl.user_followers(user_id, amount=limit)
            )
            for uid, user in list(followers.items())[:limit]:
                if not self._within_limit("dms"):
                    break
                try:
                    await loop.run_in_executor(
                        None, lambda: self.cl.direct_send(message, [uid])
                    )
                    self._count("dms")
                    log.info(f"[{self.username}] DM enviado para @{user.username}")
                    await self._human_delay(15, 40)
                except Exception:
                    pass
        except Exception as e:
            log.warning(f"[{self.username}] dm_followers_of erro: {e}")

    async def run_daily_cycle(self):
        """Ciclo completo diário de engajamento."""
        if not self._logged_in:
            if not self._login():
                return {"status": "login_failed", "username": self.username}

        hashtags = self._get_hashtags()

        for hashtag in hashtags[:3]:
            await self.follow_by_hashtag(hashtag, limit=20)
            await self.like_by_hashtag(hashtag, limit=30)
            await self.comment_by_hashtag(hashtag, limit=8)
            await self._human_delay(30, 90)

        summary = {
            "username": self.username,
            "date": datetime.now().isoformat(),
            "actions": self.daily_count,
            "status": "ok"
        }
        log.info(f"[{self.username}] Ciclo diário: {self.daily_count}")
        return summary


# ─── Multi-worker pool ────────────────────────────────────────────────────────

async def run_worker_pool(accounts: list):
    """Roda múltiplos workers em paralelo com semáforo."""
    sem = asyncio.Semaphore(MAX_WORKERS)
    results = []

    async def _run_one(account):
        async with sem:
            worker = InstagramWorker(account)
            return await worker.run_daily_cycle()

    tasks = [_run_one(acc) for acc in accounts]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results


async def load_accounts_from_db() -> list:
    """Carrega contas do banco via ELI API."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(
                f"{ELI_URL}/social/stats",
                headers={"x-jod-token": TOKEN}
            )
            return r.json().get("accounts", [])
    except Exception:
        creds_dir = Path("/app/sessions/instagram")
        accounts = []
        for f in creds_dir.glob("*/credentials.json"):
            try:
                creds = json.loads(f.read_text())
                if creds.get("status") == "created":
                    accounts.append(creds)
            except Exception:
                pass
        return accounts


async def main():
    log.info(f"Instagram Worker iniciado — NICHE={NICHE} COUNTRY={COUNTRY} MAX_WORKERS={MAX_WORKERS}")

    while True:
        accounts = await load_accounts_from_db()
        if not accounts:
            log.warning("Nenhuma conta encontrada. Aguardando 60s...")
            await asyncio.sleep(60)
            continue

        log.info(f"Iniciando ciclo para {len(accounts)} contas...")
        results = await run_worker_pool(accounts)

        successes = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "ok")
        log.info(f"Ciclo concluído: {successes}/{len(accounts)} contas OK")

        # Aguarda próximo ciclo (6 horas)
        log.info("Próximo ciclo em 6 horas...")
        await asyncio.sleep(6 * 3600)


if __name__ == "__main__":
    asyncio.run(main())
