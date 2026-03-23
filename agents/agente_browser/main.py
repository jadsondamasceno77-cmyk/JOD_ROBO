import asyncio, os, json
from playwright.async_api import async_playwright
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

TARGET = os.getenv("BROWSER_TARGET_URL", "https://example.com")

async def navigate(url=None):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url or TARGET)
        title = await page.title()
        content = await page.inner_text("body")
        await browser.close()
        return {"title": title, "content": content[:500], "url": url or TARGET}

async def screenshot(url=None):
    path = str(Path(__file__).resolve().parent.parent.parent / "memory" / "screenshot.png")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url or TARGET)
        await page.screenshot(path=path)
        await browser.close()
        return {"screenshot": path}

if __name__ == "__main__":
    r = asyncio.run(navigate())
    print(json.dumps(r, indent=2))
