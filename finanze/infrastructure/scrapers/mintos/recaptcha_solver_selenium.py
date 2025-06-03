import logging
import os
import random
import time

import aiohttp
import speech_recognition as sr
from pydub import AudioSegment
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class RecaptchaSolver:
    def __init__(self, driver, timeout=10):
        self._driver = driver
        self._timeout = timeout
        self._log = logging.getLogger(__name__)

    async def solve_captcha(self):
        try:
            # Switch to the CAPTCHA iframe
            WebDriverWait(self._driver, self._timeout).until(
                EC.frame_to_be_available_and_switch_to_it(
                    (By.XPATH, "//iframe[contains(@title, 'reCAPTCHA')]")
                )
            )

            # Click on the CAPTCHA box
            WebDriverWait(self._driver, self._timeout).until(
                EC.element_to_be_clickable((By.ID, "recaptcha-anchor"))
            ).click()

            # Check if the CAPTCHA is solved
            time.sleep(1)  # Allow some time for the state to update
            if self.is_solved():
                self._log.debug("CAPTCHA solved by clicking.")
                self._driver.switch_to.default_content()  # Switch back to main content
                return

            # If not solved, attempt audio CAPTCHA solving
            await self.solve_audio_captcha()

        except Exception as e:
            self._log.error(f"An error occurred while solving CAPTCHA: {e}")
            self._driver.switch_to.default_content()  # Ensure we switch back in case of error
            raise

    async def solve_audio_captcha(self):
        try:
            self._driver.switch_to.default_content()

            # Switch to the audio CAPTCHA iframe
            WebDriverWait(self._driver, self._timeout).until(
                EC.frame_to_be_available_and_switch_to_it(
                    (
                        By.XPATH,
                        '//iframe[@title="recaptcha challenge expires in two minutes"]',
                    )
                )
            )

            # Click on the audio button
            audio_button = WebDriverWait(self._driver, self._timeout).until(
                EC.element_to_be_clickable((By.ID, "recaptcha-audio-button"))
            )
            audio_button.click()

            # Get the audio source URL
            audio_source = (
                WebDriverWait(self._driver, self._timeout)
                .until(EC.presence_of_element_located((By.ID, "audio-source")))
                .get_attribute("src")
            )
            self._log.debug(f"Audio source URL: {audio_source}")

            # Download the audio to the temp folder asynchronously
            temp_dir = os.getenv("TEMP") if os.name == "nt" else "/tmp/"
            path_to_mp3 = os.path.normpath(
                os.path.join(temp_dir, f"{random.randrange(1, 1000)}.mp3")
            )
            path_to_wav = os.path.normpath(
                os.path.join(temp_dir, f"{random.randrange(1, 1000)}.wav")
            )

            await self.download_audio(audio_source, path_to_mp3)

            # Convert mp3 to wav
            sound = AudioSegment.from_mp3(path_to_mp3)
            sound.export(path_to_wav, format="wav")
            self._log.debug("Converted MP3 to WAV.")

            # Recognize the audio
            recognizer = sr.Recognizer()
            with sr.AudioFile(path_to_wav) as source:
                audio = recognizer.record(source)
            captcha_text = recognizer.recognize_google(audio).lower()
            self._log.debug(f"Recognized CAPTCHA text: {captcha_text}")

            # Enter the CAPTCHA text
            audio_response = WebDriverWait(self._driver, 20).until(
                EC.presence_of_element_located((By.ID, "audio-response"))
            )
            audio_response.send_keys(captcha_text)
            audio_response.send_keys(Keys.ENTER)
            self._log.debug("Entered and submitted CAPTCHA text.")

            # Wait for CAPTCHA to be processed
            time.sleep(1)

            # Verify CAPTCHA is solved
            # if self.is_solved():
            #     self._log.debug("Audio CAPTCHA solved.")
            # else:
            #     self._log.error("Failed to solve audio CAPTCHA.")
            #     raise Exception("Failed to solve CAPTCHA")

        except Exception as e:
            self._log.error(f"An error occurred while solving audio CAPTCHA: {e}")
            self._driver.switch_to.default_content()  # Ensure we switch back in case of error
            raise

        finally:
            # Always switch back to the main content
            self._driver.switch_to.default_content()

    def is_solved(self):
        try:
            # Switch back to the default content
            self._driver.switch_to.default_content()

            # Switch to the reCAPTCHA iframe
            iframe_check = self._driver.find_element(
                By.XPATH, "//iframe[contains(@title, 'reCAPTCHA')]"
            )
            self._driver.switch_to.frame(iframe_check)

            # Find the checkbox element and check its aria-checked attribute
            checkbox = WebDriverWait(self._driver, self._timeout).until(
                EC.presence_of_element_located((By.ID, "recaptcha-anchor"))
            )
            aria_checked = checkbox.get_attribute("aria-checked")

            # Return True if the aria-checked attribute is "true" or the checkbox has the 'recaptcha-checkbox-checked' class
            return (
                aria_checked == "true"
                or "recaptcha-checkbox-checked" in checkbox.get_attribute("class")
            )

        except Exception as e:
            self._log.error(
                f"An error occurred while checking if CAPTCHA is solved: {e}"
            )
            return False

    async def download_audio(self, url, path):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                with open(path, "wb") as f:
                    f.write(await response.read())
        self._log.debug("Downloaded audio asynchronously.")
