import os

from selenium import webdriver
from selenium.common import TimeoutException
from selenium.webdriver import FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from domain.entity_login import EntityLoginResult, LoginResultCode
from infrastructure.client.entity.financial.mintos.mintos_client import MintosAPIClient
from infrastructure.client.entity.financial.mintos.recaptcha_solver_selenium import (
    RecaptchaSolver,
)


def _cookies_to_header(cookies: list[dict]) -> str:
    return "; ".join(f"{c['name']}={c['value']}" for c in cookies)


async def login(
    log, inject_cookies_fn, username: str, password: str
) -> EntityLoginResult:
    driver = None

    webdriver_address = os.getenv("WEBDRIVER_ADDRESS", "http://localhost:4444")

    options = FirefoxOptions()
    options.add_argument("--headless")

    try:
        driver = webdriver.Remote(
            command_executor=webdriver_address,
            options=options,
        )

        driver.get(f"{MintosAPIClient.BASE_URL}/en/login/")

        wait = WebDriverWait(driver, 5)
        wait.until(EC.element_to_be_clickable((By.ID, "login-username")))

        username_input = driver.find_element(By.ID, "login-username")
        username_input.send_keys(username)

        password_input = driver.find_element(By.ID, "login-password")
        password_input.send_keys(password)

        password_input.send_keys(Keys.RETURN)

        wait = WebDriverWait(driver, 4)
        try:
            wait.until(
                lambda d: "overview" in d.current_url or "general" in d.current_url
            )
        except TimeoutException:
            log.info("Not redirecting to overview page, checking recaptcha.")
            recaptcha_solver = RecaptchaSolver(driver, 10)
            await recaptcha_solver.solve_audio_captcha()

        # Wait for the page to stabilize after login
        WebDriverWait(driver, 7).until(
            lambda d: "overview" in d.current_url or "general" in d.current_url
        )

        # Get cookies directly from the browser
        cookies = driver.get_cookies()
        if not cookies:
            log.error("Could not get cookies from browser")
            return EntityLoginResult(
                LoginResultCode.UNEXPECTED_ERROR,
                message="Failed to get cookies from browser",
            )

        cookie_header = _cookies_to_header(cookies)
        log.debug(f"Got {len(cookies)} cookies from browser")

        inject_cookies_fn(cookie_header)

        return EntityLoginResult(LoginResultCode.CREATED)

    except Exception as e:
        try:
            if driver:
                invalid_credentials_element = driver.find_element(
                    By.XPATH, "//*[contains(text(), 'Invalid username or password')]"
                )
                if invalid_credentials_element:
                    return EntityLoginResult(LoginResultCode.INVALID_CREDENTIALS)
        except Exception:
            pass

        log.exception(f"An error occurred while logging in: {e}")
        return EntityLoginResult(LoginResultCode.UNEXPECTED_ERROR, message=str(e))

    finally:
        if driver:
            driver.quit()
