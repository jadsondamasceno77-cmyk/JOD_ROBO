#!/usr/bin/env python3
"""
Social Playwright — 3 componentes:
  1. ProfileCreator  — cria contas reais nas redes sociais
  2. AutoPoster      — posta conteúdo usando sessões salvas
  3. CommentResponder — monitora e responde comentários com IA
"""
import os
import json
import asyncio
import random
import string
import httpx
from pathlib import Path
from datetime import datetime
from typing import Optional

from playwright.async_api import async_playwright, BrowserContext, Page

# ─── Config ───────────────────────────────────────────────────────────────────

SESSIONS_DIR = Path(__file__).resolve().parent / "sessions"
SESSIONS_DIR.mkdir(exist_ok=True)

_ELI     = "http://localhost:37779"
_TOKEN   = os.getenv("JOD_TRUST_MANIFEST", "jod_robo_trust_2026_secure")

PLATFORMS = ["instagram", "tiktok", "twitter", "linkedin", "youtube"]

# User agents por plataforma (mobile first para stories/reels)
_UA_MOBILE = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)
_UA_DESKTOP = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _rand_str(n: int) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))

def _session_path(platform: str, brand_id: int) -> Path:
    p = SESSIONS_DIR / platform / str(brand_id)
    p.mkdir(parents=True, exist_ok=True)
    return p

def _credentials_path(platform: str, brand_id: int) -> Path:
    return _session_path(platform, brand_id) / "credentials.json"

def _save_credentials(platform: str, brand_id: int, creds: dict):
    with open(_credentials_path(platform, brand_id), "w") as f:
        json.dump(creds, f, indent=2)

def _load_credentials(platform: str, brand_id: int) -> Optional[dict]:
    p = _credentials_path(platform, brand_id)
    if p.exists():
        return json.loads(p.read_text())
    return None

async def _ai_response(prompt: str) -> str:
    """Gera resposta via ELI API."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as c:
            r = await c.post(f"{_ELI}/chat",
                headers={"x-jod-token": _TOKEN, "Content-Type": "application/json"},
                json={"message": prompt, "session_id": "playwright"})
            return r.json().get("response", "")
    except Exception as e:
        return f"[AI indisponível: {e}]"

async def _human_type(page: Page, selector: str, text: str):
    """Digita como humano (delay aleatório entre teclas)."""
    await page.click(selector)
    for char in text:
        await page.keyboard.type(char)
        await asyncio.sleep(random.uniform(0.05, 0.15))

async def _wait_human(min_s: float = 1.0, max_s: float = 3.0):
    await asyncio.sleep(random.uniform(min_s, max_s))

async def _new_context(playwright, platform: str, brand_id: int,
                        mobile: bool = False) -> BrowserContext:
    """Cria contexto com sessão persistente."""
    session_dir = str(_session_path(platform, brand_id))
    browser = playwright.chromium
    ctx = await browser.launch_persistent_context(
        session_dir,
        headless=True,
        user_agent=_UA_MOBILE if mobile else _UA_DESKTOP,
        viewport={"width": 390, "height": 844} if mobile else {"width": 1280, "height": 800},
        locale="pt-BR",
        timezone_id="America/Sao_Paulo",
        args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"],
    )
    return ctx

# ─── 1. PROFILE CREATOR ───────────────────────────────────────────────────────

class ProfileCreator:
    """Cria contas reais nas redes sociais do zero."""

    async def create_all(self, brand_id: int, brand_name: str, niche: str,
                          email_base: str, password: str,
                          platforms: list = None) -> dict:
        """Cria perfis em todas as plataformas especificadas."""
        targets = platforms or PLATFORMS
        results = {}
        async with async_playwright() as pw:
            for platform in targets:
                try:
                    result = await self._create(pw, platform, brand_id,
                                                brand_name, niche, email_base, password)
                    results[platform] = result
                    await _wait_human(2, 5)
                except Exception as e:
                    results[platform] = {"status": "error", "detail": str(e)}
        return results

    async def _create(self, pw, platform: str, brand_id: int,
                       brand_name: str, niche: str,
                       email_base: str, password: str) -> dict:
        ctx = await _new_context(pw, platform, brand_id, mobile=True)
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        try:
            method = getattr(self, f"_create_{platform}", self._create_generic)
            result = await method(page, brand_id, brand_name, niche, email_base, password)
            return result
        finally:
            await ctx.close()

    # ── Instagram ────────────────────────────────────────────────────────────

    async def _create_instagram(self, page: Page, brand_id: int,
                                  brand_name: str, niche: str,
                                  email_base: str, password: str) -> dict:
        username = f"{brand_name.lower().replace(' ', '_')}_{_rand_str(4)}"
        email = f"{email_base}+ig_{brand_id}@gmail.com"

        await page.goto("https://www.instagram.com/accounts/emailsignup/")
        await _wait_human(2, 4)

        # Preenche formulário
        await _human_type(page, 'input[name="emailOrPhone"]', email)
        await _human_type(page, 'input[name="fullName"]', brand_name)
        await _human_type(page, 'input[name="username"]', username)
        await _human_type(page, 'input[name="password"]', password)
        await _wait_human()

        await page.click('button[type="submit"]')
        await _wait_human(3, 6)

        # Verifica se passou para tela de data de nascimento
        if await page.locator('input[aria-label*="Month"]').count() > 0:
            await page.select_option('select[title*="Month"]', "5")
            await page.select_option('select[title*="Day"]', "15")
            await page.select_option('select[title*="Year"]', "1995")
            await page.click('button[type="submit"]')
            await _wait_human(2, 4)

        _save_credentials("instagram", brand_id, {
            "username": username, "email": email, "password": password,
            "created_at": datetime.now().isoformat(), "status": "created"
        })

        return {"status": "created", "platform": "instagram",
                "username": username, "email": email,
                "note": "Verifique o email para confirmar a conta"}

    # ── TikTok ───────────────────────────────────────────────────────────────

    async def _create_tiktok(self, page: Page, brand_id: int,
                               brand_name: str, niche: str,
                               email_base: str, password: str) -> dict:
        email = f"{email_base}+tt_{brand_id}@gmail.com"

        await page.goto("https://www.tiktok.com/signup/phone-or-email/email")
        await _wait_human(2, 4)

        await _human_type(page, 'input[name="email"]', email)
        await _human_type(page, 'input[type="password"]', password)
        await _wait_human()

        await page.click('button[data-e2e="signup-button"]')
        await _wait_human(3, 5)

        _save_credentials("tiktok", brand_id, {
            "email": email, "password": password,
            "created_at": datetime.now().isoformat(), "status": "created"
        })

        return {"status": "created", "platform": "tiktok",
                "email": email,
                "note": "Pode requerer verificação de email ou CAPTCHA manual"}

    # ── Twitter/X ────────────────────────────────────────────────────────────

    async def _create_twitter(self, page: Page, brand_id: int,
                                brand_name: str, niche: str,
                                email_base: str, password: str) -> dict:
        email = f"{email_base}+tw_{brand_id}@gmail.com"
        username = f"{brand_name.lower().replace(' ', '')}_{_rand_str(3)}"

        await page.goto("https://twitter.com/i/flow/signup")
        await _wait_human(2, 4)

        # Passo 1: nome + email
        if await page.locator('input[autocomplete="name"]').count() > 0:
            await _human_type(page, 'input[autocomplete="name"]', brand_name)
        if await page.locator('input[autocomplete="email"]').count() > 0:
            await _human_type(page, 'input[autocomplete="email"]', email)
        await _wait_human()

        next_btn = page.locator('div[role="button"]:has-text("Next")').first
        if await next_btn.count() > 0:
            await next_btn.click()
            await _wait_human(2, 4)

        _save_credentials("twitter", brand_id, {
            "username": username, "email": email, "password": password,
            "created_at": datetime.now().isoformat(), "status": "initiated"
        })

        return {"status": "initiated", "platform": "twitter",
                "email": email, "username": username,
                "note": "Twitter requer verificação de telefone — fluxo iniciado"}

    # ── LinkedIn ──────────────────────────────────────────────────────────────

    async def _create_linkedin(self, page: Page, brand_id: int,
                                 brand_name: str, niche: str,
                                 email_base: str, password: str) -> dict:
        email = f"{email_base}+li_{brand_id}@gmail.com"
        parts = brand_name.split()
        first = parts[0] if parts else brand_name
        last = parts[-1] if len(parts) > 1 else _rand_str(4)

        await page.goto("https://www.linkedin.com/signup/cold-join")
        await _wait_human(2, 4)

        await _human_type(page, 'input#email-address', email)
        await _human_type(page, 'input#password', password)
        await _wait_human()
        await page.click('button[data-litms-control-urn*="join"]')
        await _wait_human(2, 4)

        if await page.locator('input#first-name').count() > 0:
            await _human_type(page, 'input#first-name', first)
            await _human_type(page, 'input#last-name', last)
            await _wait_human()
            await page.click('button[data-litms-control-urn*="continue"]')
            await _wait_human(2, 4)

        _save_credentials("linkedin", brand_id, {
            "email": email, "password": password, "first": first, "last": last,
            "created_at": datetime.now().isoformat(), "status": "created"
        })

        return {"status": "created", "platform": "linkedin",
                "email": email,
                "note": "Verificação de email pode ser necessária"}

    # ── YouTube (Google) ──────────────────────────────────────────────────────

    async def _create_youtube(self, page: Page, brand_id: int,
                                brand_name: str, niche: str,
                                email_base: str, password: str) -> dict:
        """YouTube usa conta Google — cria Gmail."""
        parts = brand_name.split()
        first = parts[0] if parts else brand_name
        last = parts[-1] if len(parts) > 1 else "Brand"
        username_hint = f"{first.lower()}.{last.lower()}.{_rand_str(4)}"

        await page.goto("https://accounts.google.com/signup/v2/webcreateaccount")
        await _wait_human(2, 4)

        if await page.locator('input[name="firstName"]').count() > 0:
            await _human_type(page, 'input[name="firstName"]', first)
            await _human_type(page, 'input[name="lastName"]', last)
            await page.click('button:has-text("Next")')
            await _wait_human(2, 4)

        if await page.locator('input[name="Username"]').count() > 0:
            await _human_type(page, 'input[name="Username"]', username_hint)
            await page.click('button:has-text("Next")')
            await _wait_human(2, 4)

        if await page.locator('input[name="Passwd"]').count() > 0:
            await _human_type(page, 'input[name="Passwd"]', password)
            await _human_type(page, 'input[name="PasswdAgain"]', password)
            await page.click('button:has-text("Next")')
            await _wait_human(2, 4)

        email = f"{username_hint}@gmail.com"
        _save_credentials("youtube", brand_id, {
            "email": email, "password": password, "first": first, "last": last,
            "created_at": datetime.now().isoformat(), "status": "created"
        })

        return {"status": "created", "platform": "youtube",
                "email": email,
                "note": "Google pode pedir verificação por telefone"}

    async def _create_generic(self, page: Page, brand_id: int, *args, **kwargs) -> dict:
        return {"status": "unsupported", "detail": "Plataforma não implementada"}


# ─── 2. AUTO POSTER ───────────────────────────────────────────────────────────

class AutoPoster:
    """Posta conteúdo nas redes sociais usando sessões salvas."""

    async def post(self, brand_id: int, platform: str, content: dict) -> dict:
        """
        content = {
          "caption": "...",
          "hashtags": ["#tag1", ...],
          "media_path": "/path/to/file.mp4",  # opcional
          "type": "feed" | "story" | "reel"
        }
        """
        creds = _load_credentials(platform, brand_id)
        if not creds:
            return {"status": "error", "detail": f"Sem credenciais para {platform} brand {brand_id}"}

        async with async_playwright() as pw:
            ctx = await _new_context(pw, platform, brand_id, mobile=True)
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            try:
                method = getattr(self, f"_post_{platform}", self._post_generic)
                result = await method(page, creds, content)
                return result
            except Exception as e:
                return {"status": "error", "detail": str(e)}
            finally:
                await ctx.close()

    # ── Instagram ────────────────────────────────────────────────────────────

    async def _post_instagram(self, page: Page, creds: dict, content: dict) -> dict:
        post_type = content.get("type", "feed")
        caption = content.get("caption", "") + " " + " ".join(content.get("hashtags", []))
        media_path = content.get("media_path")

        # Verifica sessão
        await page.goto("https://www.instagram.com/")
        await _wait_human(2, 3)

        # Login se necessário
        if await page.locator('input[name="username"]').count() > 0:
            await _human_type(page, 'input[name="username"]', creds["username"])
            await _human_type(page, 'input[name="password"]', creds["password"])
            await page.click('button[type="submit"]')
            await _wait_human(3, 5)

        # Clica em + (criar post)
        plus_btn = page.locator('svg[aria-label="New post"]').first
        if await plus_btn.count() > 0:
            await plus_btn.click()
            await _wait_human(1, 2)

        # Upload de mídia
        if media_path and Path(media_path).exists():
            file_input = page.locator('input[type="file"]').first
            if await file_input.count() > 0:
                await file_input.set_input_files(media_path)
                await _wait_human(2, 4)

        # Avança etapas
        for _ in range(3):
            next_btn = page.locator('button:has-text("Next")').first
            if await next_btn.count() > 0:
                await next_btn.click()
                await _wait_human(1, 2)

        # Escreve legenda
        caption_box = page.locator('div[aria-label*="caption"], textarea[aria-label*="Caption"]').first
        if await caption_box.count() > 0:
            await caption_box.click()
            await page.keyboard.type(caption)
            await _wait_human(1, 2)

        # Publica
        share_btn = page.locator('button:has-text("Share")').first
        if await share_btn.count() > 0:
            await share_btn.click()
            await _wait_human(3, 5)
            return {"status": "posted", "platform": "instagram", "type": post_type}

        return {"status": "partial", "detail": "Botão Share não encontrado — possível CAPTCHA"}

    # ── TikTok ───────────────────────────────────────────────────────────────

    async def _post_tiktok(self, page: Page, creds: dict, content: dict) -> dict:
        caption = content.get("caption", "") + " " + " ".join(content.get("hashtags", []))
        media_path = content.get("media_path")

        await page.goto("https://www.tiktok.com/upload")
        await _wait_human(2, 3)

        # Login se necessário
        if await page.locator('a:has-text("Log in")').count() > 0:
            await page.goto("https://www.tiktok.com/login/phone-or-email/email")
            await _wait_human(2, 3)
            await _human_type(page, 'input[name="email"]', creds["email"])
            await _human_type(page, 'input[type="password"]', creds["password"])
            await page.click('button[data-e2e="login-button"]')
            await _wait_human(3, 5)
            await page.goto("https://www.tiktok.com/upload")
            await _wait_human(2, 3)

        # Upload
        if media_path and Path(media_path).exists():
            file_input = page.locator('input[type="file"]').first
            if await file_input.count() > 0:
                await file_input.set_input_files(media_path)
                await _wait_human(3, 6)

        # Legenda
        caption_box = page.locator('div[contenteditable="true"]').first
        if await caption_box.count() > 0:
            await caption_box.click()
            await page.keyboard.type(caption[:2200])
            await _wait_human(1, 2)

        # Publica
        post_btn = page.locator('button:has-text("Post")').first
        if await post_btn.count() > 0:
            await post_btn.click()
            await _wait_human(3, 5)
            return {"status": "posted", "platform": "tiktok"}

        return {"status": "partial", "detail": "Botão Post não encontrado"}

    # ── Twitter ───────────────────────────────────────────────────────────────

    async def _post_twitter(self, page: Page, creds: dict, content: dict) -> dict:
        text = content.get("caption", "") + " " + " ".join(content.get("hashtags", []))
        media_path = content.get("media_path")

        await page.goto("https://twitter.com/compose/tweet")
        await _wait_human(2, 3)

        # Login se necessário
        if await page.locator('input[autocomplete="username"]').count() > 0:
            await _human_type(page, 'input[autocomplete="username"]', creds["email"])
            await page.click('div[role="button"]:has-text("Next")')
            await _wait_human(1, 2)
            await _human_type(page, 'input[name="password"]', creds["password"])
            await page.click('div[data-testid="LoginForm_Login_Button"]')
            await _wait_human(3, 5)
            await page.goto("https://twitter.com/compose/tweet")
            await _wait_human(1, 2)

        # Escreve tweet
        tweet_box = page.locator('div[data-testid="tweetTextarea_0"]').first
        if await tweet_box.count() > 0:
            await tweet_box.click()
            await page.keyboard.type(text[:280])
            await _wait_human(1, 2)

        # Upload mídia
        if media_path and Path(media_path).exists():
            media_btn = page.locator('input[data-testid="fileInput"]').first
            if await media_btn.count() > 0:
                await media_btn.set_input_files(media_path)
                await _wait_human(2, 4)

        # Posta
        tweet_btn = page.locator('div[data-testid="tweetButtonInline"]').first
        if await tweet_btn.count() > 0:
            await tweet_btn.click()
            await _wait_human(2, 4)
            return {"status": "posted", "platform": "twitter"}

        return {"status": "partial", "detail": "Botão Tweet não encontrado"}

    # ── LinkedIn ──────────────────────────────────────────────────────────────

    async def _post_linkedin(self, page: Page, creds: dict, content: dict) -> dict:
        text = content.get("caption", "") + "\n\n" + " ".join(content.get("hashtags", []))

        await page.goto("https://www.linkedin.com/feed/")
        await _wait_human(2, 3)

        # Login se necessário
        if await page.locator('input#username').count() > 0:
            await _human_type(page, 'input#username', creds["email"])
            await _human_type(page, 'input#password', creds["password"])
            await page.click('button[type="submit"]')
            await _wait_human(3, 5)

        # Clicar em "Iniciar uma publicação"
        post_btn = page.locator('button.share-box-feed-entry__trigger').first
        if await post_btn.count() == 0:
            post_btn = page.locator('span:has-text("Start a post")').first
        if await post_btn.count() > 0:
            await post_btn.click()
            await _wait_human(1, 2)

        # Escreve conteúdo
        editor = page.locator('div.ql-editor, div[contenteditable="true"]').first
        if await editor.count() > 0:
            await editor.click()
            await page.keyboard.type(text[:3000])
            await _wait_human(1, 2)

        # Publica
        publish_btn = page.locator('button.share-actions__primary-action').first
        if await publish_btn.count() > 0:
            await publish_btn.click()
            await _wait_human(2, 4)
            return {"status": "posted", "platform": "linkedin"}

        return {"status": "partial", "detail": "Botão Post não encontrado"}

    async def _post_youtube(self, page: Page, creds: dict, content: dict) -> dict:
        """YouTube upload via Studio."""
        media_path = content.get("media_path")
        if not media_path or not Path(media_path).exists():
            return {"status": "error", "detail": "Mídia necessária para YouTube"}

        title = content.get("caption", "Novo vídeo")[:100]
        description = content.get("caption", "") + "\n\n" + " ".join(content.get("hashtags", []))

        await page.goto("https://studio.youtube.com/")
        await _wait_human(3, 5)

        upload_btn = page.locator('ytcp-button#upload-icon').first
        if await upload_btn.count() > 0:
            await upload_btn.click()
            await _wait_human(1, 2)

        file_input = page.locator('input#content').first
        if await file_input.count() > 0:
            await file_input.set_input_files(media_path)
            await _wait_human(5, 10)

        title_box = page.locator('div#textbox[aria-label*="title"]').first
        if await title_box.count() > 0:
            await title_box.triple_click()
            await page.keyboard.type(title)

        desc_box = page.locator('div#textbox[aria-label*="description"]').first
        if await desc_box.count() > 0:
            await desc_box.click()
            await page.keyboard.type(description[:5000])

        for _ in range(3):
            next_btn = page.locator('ytcp-button:has-text("Next")').first
            if await next_btn.count() > 0:
                await next_btn.click()
                await _wait_human(1, 2)

        publish_btn = page.locator('ytcp-button:has-text("Publish")').first
        if await publish_btn.count() > 0:
            await publish_btn.click()
            await _wait_human(3, 5)
            return {"status": "posted", "platform": "youtube"}

        return {"status": "partial", "detail": "Botão Publish não encontrado"}

    async def _post_generic(self, page, creds, content) -> dict:
        return {"status": "unsupported"}


# ─── 3. COMMENT RESPONDER ─────────────────────────────────────────────────────

class CommentResponder:
    """Monitora e responde comentários com IA."""

    async def respond(self, brand_id: int, platform: str,
                       brand_context: str = "", max_comments: int = 10) -> dict:
        """Lê e responde comentários novos."""
        creds = _load_credentials(platform, brand_id)
        if not creds:
            return {"status": "error", "detail": f"Sem credenciais para {platform}"}

        async with async_playwright() as pw:
            ctx = await _new_context(pw, platform, brand_id, mobile=True)
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            try:
                method = getattr(self, f"_respond_{platform}", self._respond_generic)
                result = await method(page, creds, brand_context, max_comments)
                return result
            except Exception as e:
                return {"status": "error", "detail": str(e)}
            finally:
                await ctx.close()

    async def _generate_reply(self, comment: str, brand_context: str) -> str:
        """Gera resposta via ELI."""
        prompt = (
            f"Você é um gestor de comunidade profissional. Responda este comentário de forma "
            f"autêntica, engajadora e alinhada com a marca.\n\n"
            f"Contexto da marca: {brand_context}\n\n"
            f"Comentário: {comment}\n\n"
            f"Resposta (máx 150 caracteres, sem hashtags):"
        )
        reply = await _ai_response(prompt)
        return reply.strip()[:150]

    # ── Instagram ────────────────────────────────────────────────────────────

    async def _respond_instagram(self, page: Page, creds: dict,
                                   brand_context: str, max_comments: int) -> dict:
        responded = []

        await page.goto("https://www.instagram.com/")
        await _wait_human(2, 3)

        # Login se necessário
        if await page.locator('input[name="username"]').count() > 0:
            await _human_type(page, 'input[name="username"]', creds["username"])
            await _human_type(page, 'input[name="password"]', creds["password"])
            await page.click('button[type="submit"]')
            await _wait_human(3, 5)

        # Vai para notificações
        await page.goto("https://www.instagram.com/")
        notif_btn = page.locator('svg[aria-label="Notifications"]').first
        if await notif_btn.count() > 0:
            await notif_btn.click()
            await _wait_human(2, 3)

        # Captura comentários visíveis nas notificações
        comment_items = await page.locator('div[role="button"]:has-text("commented")').all()

        for item in comment_items[:max_comments]:
            try:
                text = await item.inner_text()
                # Extrai o comentário (texto depois de "commented:")
                if "commented" in text:
                    comment_text = text.split("commented")[-1].strip()[:200]
                    reply = await self._generate_reply(comment_text, brand_context)

                    # Clica no item para abrir o post
                    await item.click()
                    await _wait_human(2, 3)

                    # Procura caixa de reply
                    reply_btn = page.locator('button:has-text("Reply")').first
                    if await reply_btn.count() > 0:
                        await reply_btn.click()
                        await _wait_human(1, 2)
                        await page.keyboard.type(reply)
                        await _wait_human(1, 2)
                        await page.keyboard.press("Enter")
                        responded.append({"comment": comment_text[:50], "reply": reply})
                        await _wait_human(3, 6)  # Evita rate limit

                    await page.go_back()
                    await _wait_human(1, 2)
            except Exception:
                continue

        return {"status": "ok", "platform": "instagram", "responded": len(responded),
                "details": responded}

    # ── Twitter ───────────────────────────────────────────────────────────────

    async def _respond_twitter(self, page: Page, creds: dict,
                                 brand_context: str, max_comments: int) -> dict:
        responded = []

        await page.goto("https://twitter.com/notifications/mentions")
        await _wait_human(2, 3)

        if await page.locator('input[autocomplete="username"]').count() > 0:
            await _human_type(page, 'input[autocomplete="username"]', creds["email"])
            await page.click('div[role="button"]:has-text("Next")')
            await _wait_human(1, 2)
            await _human_type(page, 'input[name="password"]', creds["password"])
            await page.click('div[data-testid="LoginForm_Login_Button"]')
            await _wait_human(3, 5)
            await page.goto("https://twitter.com/notifications/mentions")
            await _wait_human(2, 3)

        tweets = await page.locator('article[data-testid="tweet"]').all()

        for tweet in tweets[:max_comments]:
            try:
                text_el = tweet.locator('div[data-testid="tweetText"]').first
                if await text_el.count() > 0:
                    comment_text = await text_el.inner_text()
                    reply = await self._generate_reply(comment_text, brand_context)

                    reply_btn = tweet.locator('div[data-testid="reply"]').first
                    if await reply_btn.count() > 0:
                        await reply_btn.click()
                        await _wait_human(1, 2)
                        tweet_box = page.locator('div[data-testid="tweetTextarea_0"]').first
                        if await tweet_box.count() > 0:
                            await tweet_box.click()
                            await page.keyboard.type(reply[:280])
                            await _wait_human(1, 2)
                            post_btn = page.locator('div[data-testid="tweetButtonInline"]').first
                            if await post_btn.count() > 0:
                                await post_btn.click()
                                responded.append({"comment": comment_text[:50], "reply": reply})
                                await _wait_human(3, 6)
            except Exception:
                continue

        return {"status": "ok", "platform": "twitter", "responded": len(responded),
                "details": responded}

    # ── TikTok ───────────────────────────────────────────────────────────────

    async def _respond_tiktok(self, page: Page, creds: dict,
                                brand_context: str, max_comments: int) -> dict:
        responded = []

        await page.goto("https://www.tiktok.com/")
        await _wait_human(2, 3)

        # Login se necessário
        if await page.locator('a:has-text("Log in")').count() > 0:
            await page.goto("https://www.tiktok.com/login/phone-or-email/email")
            await _wait_human(2, 3)
            await _human_type(page, 'input[name="email"]', creds["email"])
            await _human_type(page, 'input[type="password"]', creds["password"])
            await page.click('button[data-e2e="login-button"]')
            await _wait_human(3, 5)

        await page.goto("https://www.tiktok.com/notification")
        await _wait_human(2, 3)

        comment_notifs = await page.locator('div[data-e2e="comment-notification"]').all()

        for notif in comment_notifs[:max_comments]:
            try:
                text = await notif.inner_text()
                reply = await self._generate_reply(text[:200], brand_context)
                # TikTok requer abrir o post para responder
                await notif.click()
                await _wait_human(2, 3)

                reply_box = page.locator('div[data-e2e="comment-input"]').first
                if await reply_box.count() > 0:
                    await reply_box.click()
                    await page.keyboard.type(reply[:150])
                    await _wait_human(1, 2)
                    await page.keyboard.press("Enter")
                    responded.append({"comment": text[:50], "reply": reply})
                    await _wait_human(3, 6)

                await page.go_back()
                await _wait_human(1, 2)
            except Exception:
                continue

        return {"status": "ok", "platform": "tiktok", "responded": len(responded),
                "details": responded}

    async def _respond_generic(self, page, creds, brand_context, max_comments) -> dict:
        return {"status": "unsupported"}


# ─── Entrypoints públicos ─────────────────────────────────────────────────────

async def create_profile(brand_id: int, brand_name: str, niche: str,
                          email_base: str, password: str,
                          platforms: list = None) -> dict:
    creator = ProfileCreator()
    return await creator.create_all(brand_id, brand_name, niche, email_base, password, platforms)


async def auto_post(brand_id: int, platform: str, content: dict) -> dict:
    poster = AutoPoster()
    return await poster.post(brand_id, platform, content)


async def respond_comments(brand_id: int, platform: str,
                             brand_context: str = "", max_comments: int = 10) -> dict:
    responder = CommentResponder()
    return await responder.respond(brand_id, platform, brand_context, max_comments)
