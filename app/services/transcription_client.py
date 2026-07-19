import logging
import os
from typing import Optional

import requests
from flask import current_app

logger = logging.getLogger(__name__)


class TranscriptionClient:
    """Client for the whisper.cpp transcription microservice.

    Sends audio files to the transcription container and returns
    the transcribed text.
    """

    def __init__(self):
        self.timeout = 60  # seconds - generous for longer recordings

    @property
    def base_url(self) -> str:
        return current_app.config.get(
            "TRANSCRIPTION_URL", "http://transcriber:8080"
        )

    @property
    def inference_url(self) -> str:
        return f"{self.base_url}/inference"

    def transcribe(self, audio_file_path: str) -> Optional[str]:
        """Transcribe an audio file.

        Args:
            audio_file_path: Absolute path to the audio file on disk.

        Returns:
            Transcribed text, or None if transcription failed.
        """
        if not os.path.exists(audio_file_path):
            logger.error(f"Audio file not found: {audio_file_path}")
            return None

        try:
            with open(audio_file_path, "rb") as f:
                files = {"file": (os.path.basename(audio_file_path), f)}
                data = {
                    "temperature": "0.0",
                    "temperature_inc": "0.2",
                    "response_format": "json",
                }

                response = requests.post(
                    self.inference_url,
                    files=files,
                    data=data,
                    timeout=self.timeout,
                )

            if response.status_code != 200:
                logger.error(
                    f"Transcription service returned {response.status_code}: "
                    f"{response.text}"
                )
                return None

            result = response.json()
            text = result.get("text", "").strip()

            if not text:
                logger.warning("Transcription returned empty text")
                return None

            return text

        except requests.ConnectionError:
            logger.error(
                f"Cannot connect to transcription service at {self.inference_url}"
            )
            return None
        except requests.Timeout:
            logger.error("Transcription service timed out")
            return None
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return None

    def is_available(self) -> bool:
        """Check if the transcription service is reachable."""
        try:
            response = requests.get(self.base_url, timeout=5)
            return response.status_code == 200
        except Exception:
            return False
