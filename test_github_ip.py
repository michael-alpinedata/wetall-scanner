import asyncio
from playwright.async_api import async_playwright


async def test_site(page, url, name):
    print(f"Tentative sur {name} : {url}")
    try:
        # Injection d'un User-Agent de navigateur classique
        await page.set_extra_http_headers(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            }
        )

        response = await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        print(f"[{name}] Code HTTP reçu : {response.status}")

        content = await page.content()
        if "access denied" in content.lower() or "cloudflare" in content.lower():
            print(
                f"❌ [{name}] Bloqué par un anti-bot (détection Cloudflare/WAF dans le HTML)."
            )
        elif response.status == 200:
            print(f"✅ [{name}] Succès ! La page a chargé correctement.")
        else:
            print(f"⚠️ [{name}] Code HTTP suspect : {response.status}")

    except Exception as e:
        print(f"❌ [{name}] Échec critique : {e}")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800}, locale="fr-FR"
        )
        page = await context.new_page()

        # Test sur Wetall et un marchand type
        await test_site(page, "https://www.wetall.fr/", "Wetall Home")
        await test_site(page, "https://www.decathlon.fr/", "Decathlon Home")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
