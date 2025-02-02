from playwright.async_api import async_playwright

from domain.scrap_result import LoginResult
from infrastructure.scrapers.mintos.mintos_client import MintosAPIClient
from infrastructure.scrapers.mintos.recaptcha_solver_playwright import RecaptchaSolver


async def login(session, username: str, password: str) -> dict:
    async with async_playwright() as p:
        # browser = await p.firefox.connect('ws://localhost:3000/firefox/playwright')
        # Only working in non-headless mode, so mostly no useful
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            await page.goto(f"{MintosAPIClient.BASE_URL}/en/login/", timeout=10000)

            await page.wait_for_selector("#login-username", state="visible", timeout=5000)
            await page.fill("#login-username", username)
            await page.fill("#login-password", password)

            await page.press("#login-password", "Enter")

            try:
                await page.wait_for_url(lambda url: "overview" in url, timeout=4000)
            except Exception:
                print("Not redirecting to overview page, checking recaptcha.")
                recaptcha_solver = RecaptchaSolver(page, 10)
                await recaptcha_solver.solve_audio_captcha()

            user_request = await context.wait_for_event("request",
                                                        predicate=lambda req: MintosAPIClient.USER_PATH in req.url,
                                                        timeout=10000)

            session.headers["Cookie"] = user_request.headers["cookie"]

            return {"result": LoginResult.CREATED}

        except Exception as e:
            print(f"An error occurred while logging in: {e}")
            raise

        finally:
            await browser.close()
