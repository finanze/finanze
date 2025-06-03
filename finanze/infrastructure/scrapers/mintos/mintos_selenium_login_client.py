import os

from selenium.common import TimeoutException
from selenium.webdriver import FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from seleniumwire import webdriver

from domain.entity_login import EntityLoginResult, LoginResultCode
from infrastructure.scrapers.mintos.mintos_client import MintosAPIClient
from infrastructure.scrapers.mintos.recaptcha_solver_selenium import RecaptchaSolver


async def login(
    log, inject_cookies_fn, username: str, password: str
) -> EntityLoginResult:
    driver = None

    options = FirefoxOptions()
    options.add_argument("--headless")

    wire_address = os.getenv("WIRE_ADDRESS", "127.0.0.1")
    wire_port = int(os.getenv("WIRE_PORT", "8088"))
    proxy_address = os.getenv("WIRE_PROXY_SERVER_ADDRESS", "host.docker.internal")
    webdriver_address = os.getenv("WEBDRIVER_ADDRESS", "http://localhost:4444")

    options.set_preference("network.proxy.type", 1)
    options.set_preference("network.proxy.http", proxy_address)
    options.set_preference("network.proxy.http_port", wire_port)
    options.set_preference("network.proxy.ssl", proxy_address)
    options.set_preference("network.proxy.ssl_port", wire_port)

    wire_options = {
        "auto_config": False,
        "port": wire_port,
        "addr": wire_address,
    }

    try:
        driver = webdriver.Remote(
            command_executor=webdriver_address,
            options=options,
            seleniumwire_options=wire_options,
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
            wait.until(EC.url_contains("overview"))
        except TimeoutException:
            log.info("Not redirecting to overview page, checking recaptcha.")
            recaptcha_solver = RecaptchaSolver(driver, 10)
            await recaptcha_solver.solve_audio_captcha()

        driver.wait_for_request(MintosAPIClient.USER_PATH, timeout=5)

        user_request = next(x for x in driver.requests if "/webapp-api/user" in x.url)

        inject_cookies_fn(user_request.headers["Cookie"])

        return EntityLoginResult(LoginResultCode.CREATED)

    except Exception as e:
        invalid_credentials_element = driver.find_element(
            By.XPATH, "//*[contains(text(), 'Invalid username or password')]"
        )
        if invalid_credentials_element:
            return EntityLoginResult(LoginResultCode.INVALID_CREDENTIALS)

        log.error(f"An error occurred while logging in: {e}")
        return EntityLoginResult(LoginResultCode.UNEXPECTED_ERROR, message=str(e))

    finally:
        if driver:
            driver.quit()
