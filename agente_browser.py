#!/usr/bin/env python3
"""
JOD_ROBO — agente_browser v2.0
Capacidades: navegar, clicar, preencher, esperar, extrair, screenshot, pipeline.
"""
import asyncio, json, os, sys
from pathlib import Path
from typing import Optional
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

HEADLESS = True
TIMEOUT_MS = 15_000
SCREENSHOT_DIR = Path("/tmp/jod_screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

def ok(data): return {"status": "ok", **data}
def err(msg, detail=""): return {"status": "error", "message": msg, "detail": detail}

class BrowserAgent:
    def __init__(self):
        self._pw = self._browser = self._page = None

    async def start(self):
        self._pw      = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=HEADLESS)
        self._page    = await self._browser.new_page()
        self._page.set_default_timeout(TIMEOUT_MS)

    async def stop(self):
        if self._browser: await self._browser.close()
        if self._pw:      await self._pw.stop()

    def _loc(self, selector, by):
        match by:
            case "text":        return self._page.get_by_text(selector, exact=False)
            case "placeholder": return self._page.get_by_placeholder(selector)
            case "role":        return self._page.get_by_role(selector)
            case "label":       return self._page.get_by_label(selector)
            case "testid":      return self._page.get_by_test_id(selector)
            case _:             return self._page.locator(selector)

    async def navigate(self, url):
        try:
            resp  = await self._page.goto(url, wait_until="domcontentloaded")
            title = await self._page.title()
            return ok({"url": url, "title": title, "status_code": resp.status if resp else None})
        except Exception as e: return err("navigate_failed", str(e))

    async def click(self, selector, by="css"):
        try:
            loc = self._loc(selector, by)
            await loc.wait_for(state="visible", timeout=TIMEOUT_MS)
            await loc.click()
            return ok({"clicked": selector})
        except PWTimeout: return err("click_timeout", f"'{selector}' invisível em {TIMEOUT_MS}ms")
        except Exception as e: return err("click_failed", str(e))

    async def fill(self, selector, value, by="css"):
        try:
            loc = self._loc(selector, by)
            await loc.wait_for(state="visible", timeout=TIMEOUT_MS)
            await loc.fill(value)
            return ok({"filled": selector, "value": value})
        except PWTimeout: return err("fill_timeout", f"'{selector}' invisível")
        except Exception as e: return err("fill_failed", str(e))

    async def press(self, key, selector=None, by="css"):
        try:
            if selector: await self._loc(selector, by).press(key)
            else:        await self._page.keyboard.press(key)
            return ok({"pressed": key})
        except Exception as e: return err("press_failed", str(e))

    async def wait_for(self, selector, by="css", state="visible"):
        try:
            await self._loc(selector, by).wait_for(state=state, timeout=TIMEOUT_MS)
            return ok({"selector": selector, "state": state})
        except PWTimeout: return err("wait_timeout", f"'{selector}' não atingiu '{state}'")
        except Exception as e: return err("wait_failed", str(e))

    async def get_text(self, selector, by="css"):
        try:
            return ok({"text": (await self._loc(selector, by).inner_text()).strip()})
        except Exception as e: return err("get_text_failed", str(e))

    async def get_page_text(self):
        try:
            return ok({"text": (await self._page.inner_text("body")).strip()[:5000]})
        except Exception as e: return err("get_page_text_failed", str(e))

    async def screenshot(self, name="screenshot"):
        path = SCREENSHOT_DIR / f"{name}.png"
        try:
            await self._page.screenshot(path=str(path), full_page=True)
            return ok({"path": str(path)})
        except Exception as e: return err("screenshot_failed", str(e))

    async def current_url(self):
        return ok({"url": self._page.url})

    async def run_pipeline(self, steps):
        results = []
        for i, step in enumerate(steps):
            r = await self._dispatch(step)
            results.append({"step": i, "action": step.get("action"), **r})
            if r.get("status") == "error":
                results.append({"step": "abort", "reason": f"Erro no step {i}"})
                break
        return results

    async def _dispatch(self, step):
        match step.get("action",""):
            case "navigate":     return await self.navigate(step["url"])
            case "click":        return await self.click(step["selector"], step.get("by","css"))
            case "fill":         return await self.fill(step["selector"], step["value"], step.get("by","css"))
            case "press":        return await self.press(step["key"], step.get("selector"), step.get("by","css"))
            case "wait_for":     return await self.wait_for(step["selector"], step.get("by","css"), step.get("state","visible"))
            case "get_text":     return await self.get_text(step["selector"], step.get("by","css"))
            case "get_page_text":return await self.get_page_text()
            case "screenshot":   return await self.screenshot(step.get("name","screenshot"))
            case "current_url":  return await self.current_url()
            case _:              return err("unknown_action", step.get("action",""))

async def run_browser_task(steps):
    agent = BrowserAgent()
    await agent.start()
    try:
        results = await agent.run_pipeline(steps)
        success = all(r.get("status") != "error" for r in results if "status" in r)
        return {"status": "ok" if success else "partial_error", "results": results}
    finally:
        await agent.stop()

# Compatibilidade com x-mom.py (browser_navigate / browser_screenshot)
async def navigate(url):
    agent = BrowserAgent()
    await agent.start()
    try:
        r = await agent.navigate(url)
        text_r = await agent.get_page_text()
        return {**r, "content": text_r.get("text","") if text_r.get("status")=="ok" else ""}
    finally:
        await agent.stop()

async def screenshot(url):
    agent = BrowserAgent()
    await agent.start()
    try:
        await agent.navigate(url)
        r = await agent.screenshot("snap")
        return {"screenshot": r.get("path","")}
    finally:
        await agent.stop()

if __name__ == "__main__":
    demo = sys.argv[1] if len(sys.argv) > 1 else None
    if demo:
        payload = json.loads(demo)
        result  = asyncio.run(run_browser_task(payload["steps"]))
    else:
        result = asyncio.run(run_browser_task([
            {"action":"navigate",   "url":"https://example.com"},
            {"action":"get_text",   "selector":"h1"},
            {"action":"screenshot", "name":"demo"},
        ]))
    print(json.dumps(result, ensure_ascii=False, indent=2))
