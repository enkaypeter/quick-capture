import re
from typing import Optional

from app.repositories.case_repository import CaseRepository


class IdentifierService:
    """Generates unique identifiers for cases.

    Format: LOC-Keyword-001
    Where:
      - LOC is derived from the What3Words location (first word)
      - Keyword is extracted from the case notes or transcription
      - 001 is a sequential number
    """

    def __init__(self):
        self.case_repo = CaseRepository()

    def generate(
        self,
        location_w3w: Optional[str] = None,
        notes: Optional[str] = None,
        transcript: Optional[str] = None,
    ) -> str:
        """Generate a unique identifier for a case.

        Args:
            location_w3w: What3Words address (e.g. "filled.count.soap")
            notes: Case notes text (may contain HTML)
            transcript: Voice note transcription text
        """
        loc_part = self._extract_location_part(location_w3w)
        keyword = self._extract_keyword(notes, transcript)
        prefix = f"{loc_part}-{keyword}"
        sequence = self.case_repo.count_by_location_prefix(prefix) + 1
        return f"{prefix}-{sequence:03d}"

    def _extract_location_part(self, location_w3w: Optional[str]) -> str:
        """Extract the first word from a What3Words address."""
        if not location_w3w:
            return "UNK"

        # What3Words format: "word.word.word"
        parts = location_w3w.split(".")
        if parts:
            return parts[0].upper()[:8]
        return "UNK"

    def _extract_keyword(
        self, notes: Optional[str], transcript: Optional[str]
    ) -> str:
        """Extract a meaningful keyword from notes or transcript.

        Strips HTML tags and picks the first meaningful word (>3 chars).
        """
        text = ""
        if notes:
            # Strip HTML tags
            text = re.sub(r"<[^>]+>", " ", notes)
        elif transcript:
            text = transcript

        if not text.strip():
            return "INTERACTION"

        # Find first word longer than 3 characters
        words = re.findall(r"[a-zA-Z]{4,}", text)
        if words:
            return words[0].upper()[:10]

        return "INTERACTION"
