import logging
import os
import random

import aiohttp
import speech_recognition as sr
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError
from pydub import AudioSegment


class RecaptchaSolver:
    def __init__(self, page: Page, timeout=10):
        self._page = page
        self._timeout = timeout * 1000
        self._log = logging.getLogger(__name__)

    async def solve_captcha(self):
        try:
            # Switch to the main CAPTCHA iframe
            captcha_frame = self._page.frame_locator(
                "//iframe[contains(@title, 'reCAPTCHA')]"
            )

            # Click on the CAPTCHA checkbox
            await captcha_frame.locator("#recaptcha-anchor").click(
                timeout=self._timeout
            )

            # Check if already solved
            if await self.is_solved():
                self._log.debug("CAPTCHA solved by initial click")
                return

            # If not solved, handle audio challenge
            await self.solve_audio_captcha()

        except Exception as e:
            self._log.error(f"Error solving CAPTCHA: {e}")
            raise

    async def solve_audio_captcha(self):
        try:
            # Switch to audio challenge iframe
            challenge_frame = self._page.frame_locator(
                '//iframe[@title="recaptcha challenge expires in two minutes"]'
            )

            # Click audio button
            await challenge_frame.locator("#recaptcha-audio-button").click(
                timeout=self._timeout
            )

            # Get audio URL
            audio_src = await challenge_frame.locator("#audio-source").get_attribute(
                "src"
            )
            self._log.debug(f"Audio source URL: {audio_src}")

            # Download and process audio
            temp_dir = os.getenv("TEMP") if os.name == "nt" else "/tmp/"
            path_to_mp3 = os.path.join(temp_dir, f"{random.randrange(1, 1000)}.mp3")
            path_to_wav = os.path.join(temp_dir, f"{random.randrange(1, 1000)}.wav")

            await self.download_audio(audio_src, path_to_mp3)

            # Convert to WAV
            sound = AudioSegment.from_mp3(path_to_mp3)
            sound.export(path_to_wav, format="wav")
            self._log.debug("Converted to WAV")

            # Recognize audio
            recognizer = sr.Recognizer()
            with sr.AudioFile(path_to_wav) as source:
                audio = recognizer.record(source)
            captcha_text = recognizer.recognize_google(audio).lower()
            self._log.debug(f"Recognized text: {captcha_text}")

            # Enter text and submit
            await challenge_frame.locator("#audio-response").fill(captcha_text)
            await challenge_frame.locator("#audio-response").press("Enter")

            # Wait for verification
            await self._page.wait_for_timeout(1000)

            # if not await self.is_solved():
            #    raise Exception("Failed to solve audio CAPTCHA")

        except Exception as e:
            self._log.error(f"Error solving audio CAPTCHA: {e}")
            raise

    async def is_solved(self):
        try:
            captcha_frame = self._page.frame_locator(
                "//iframe[contains(@title, 'reCAPTCHA')]"
            )
            checkbox = captcha_frame.locator("#recaptcha-anchor")

            # Check aria-checked state
            aria_checked = await checkbox.get_attribute("aria-checked")
            if aria_checked == "true":
                return True

            # Check class list
            class_list = await checkbox.get_attribute("class")
            return "recaptcha-checkbox-checked" in class_list

        except PlaywrightTimeoutError:
            return False

    async def download_audio(self, url, path):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                with open(path, "wb") as f:
                    f.write(await response.read())
        self._log.debug("Downloaded audio asynchronously.")
