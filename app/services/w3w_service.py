import logging
from typing import Optional, Tuple

import requests as http_requests
from flask import current_app


class W3WService:
    """Service for interacting with the What3Words API (Free plan).

    The Free plan provides access to the AutoSuggest endpoint only.
    This service encapsulates the autosuggest call, keeping the API key server-side.
    """

    BASE_URL = "https://api.what3words.com/v3"
    TIMEOUT = 10

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def _get_api_key(self) -> str:
        """Retrieve the W3W API key from app configuration."""
        return current_app.config.get("W3W_API_KEY", "")

    def autosuggest(
        self,
        input_text: str,
        focus_lat: Optional[float] = None,
        focus_lng: Optional[float] = None,
        clip_to_country: Optional[str] = None,
        language: str = "en",
    ) -> Tuple[Optional[list], Optional[str]]:
        """Get autosuggest results for a partial What3Words address.

        The input must contain at least the first two words and the first
        character of the third word (e.g. "filled.count.s").

        Args:
            input_text: Partial or full 3 word address
            focus_lat: Optional latitude to prioritise nearby results
            focus_lng: Optional longitude to prioritise nearby results
            clip_to_country: Optional comma-separated country codes (e.g. "GB")
            language: Fallback language for ambiguous input (default: en)

        Returns:
            Tuple of (suggestions_list, error_message).
            Each suggestion contains: words, nearestPlace, country, rank
        """
        api_key = self._get_api_key()
        if not api_key:
            self.logger.error("W3W API key not configured")
            return None, "Location service unavailable"

        params = {
            "input": input_text,
            "key": api_key,
            "language": language,
        }

        if focus_lat is not None and focus_lng is not None:
            params["focus"] = f"{focus_lat},{focus_lng}"

        if clip_to_country:
            params["clip-to-country"] = clip_to_country

        try:
            response = http_requests.get(
                f"{self.BASE_URL}/autosuggest",
                params=params,
                timeout=self.TIMEOUT,
            )

            if response.status_code != 200:
                self.logger.error(
                    f"W3W autosuggest returned {response.status_code}: {response.text}"
                )
                return None, "Location service unavailable"

            data = response.json()

            if "error" in data:
                error_msg = data["error"].get("message", "Unknown error")
                self.logger.error(f"W3W autosuggest error: {error_msg}")
                return None, "Location service unavailable"

            suggestions = []
            for s in data.get("suggestions", []):
                suggestions.append({
                    "words": s.get("words"),
                    "nearestPlace": s.get("nearestPlace"),
                    "country": s.get("country"),
                    "rank": s.get("rank"),
                })

            return suggestions, None

        except http_requests.Timeout:
            self.logger.error("W3W autosuggest request timed out")
            return None, "Location service unavailable"
        except Exception as e:
            self.logger.error(f"W3W autosuggest failed: {e}")
            return None, "Location service unavailable"
