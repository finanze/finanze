from playwright.async_api import async_playwright

from domain.entity_login import EntityLoginResult, LoginResultCode
from infrastructure.client.entity.mintos.mintos_client import MintosAPIClient
from infrastructure.client.entity.mintos.recaptcha_solver_playwright import (
    RecaptchaSolver,
)


async def login(
    log, inject_cookies_fn, username: str, password: str
) -> EntityLoginResult:
    async with async_playwright() as p:
        # browser = await p.firefox.connect('ws://localhost:3000/firefox/playwright')
        # Only working in non-headless mode, so mostly no useful
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            await page.goto(f"{MintosAPIClient.BASE_URL}/en/login/", timeout=10000)

            await page.wait_for_selector(
                "#login-username", state="visible", timeout=5000
            )
            await page.fill("#login-username", username)
            await page.fill("#login-password", password)

            await page.press("#login-password", "Enter")

            try:
                await page.wait_for_url(lambda url: "overview" in url, timeout=4000)
            except Exception:
                log.info("Not redirecting to overview page, checking recaptcha.")
                recaptcha_solver = RecaptchaSolver(page, 10)
                await recaptcha_solver.solve_audio_captcha()

            user_request = await context.wait_for_event(
                "request",
                predicate=lambda req: MintosAPIClient.USER_PATH in req.url,
                timeout=10000,
            )

            inject_cookies_fn(user_request.headers["cookie"])

            return EntityLoginResult(LoginResultCode.CREATED)

        except Exception as e:
            log.error(f"An error occurred while logging in: {e}")
            return EntityLoginResult(LoginResultCode.UNEXPECTED_ERROR, message=str(e))

        finally:
            await browser.close()
