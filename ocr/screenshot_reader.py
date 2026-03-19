"""
ocr/screenshot_reader.py

Optional OCR module to extract conversation text from
chat screenshot images.

Requirements:
  - System: sudo apt install tesseract-ocr
  - Python: pip install pytesseract Pillow

If Tesseract is not installed, the module still loads but
raises a clear ImportError only when read_image() is called.
"""

import re
from pathlib import Path
from typing import Union


class ScreenshotReader:
    """
    Reads chat screenshots using Tesseract OCR and parses
    them into structured conversation lines.
    """

    def __init__(self, lang: str = "eng") -> None:
        """
        Args:
            lang: Tesseract language code (default: 'eng').
        """
        self.lang = lang
        self._tesseract_available: bool | None = None

    def _check_tesseract(self) -> bool:
        if self._tesseract_available is None:
            try:
                import pytesseract
                pytesseract.get_tesseract_version()
                self._tesseract_available = True
            except Exception:
                self._tesseract_available = False
        return self._tesseract_available

    # ── Public API ────────────────────────────────────────────────────────────

    def read_image(self, source: Union[str, Path, "PIL.Image.Image"]) -> str:
        """
        Extract raw text from a screenshot image.

        Args:
            source: Path to image file OR a PIL Image object.

        Returns:
            Raw extracted text string.

        Raises:
            ImportError:  if pytesseract/Tesseract is not installed.
            FileNotFoundError: if path does not exist.
        """
        if not self._check_tesseract():
            raise ImportError(
                "Tesseract OCR is not available. Install it with:\n"
                "  sudo apt install tesseract-ocr\n"
                "  pip install pytesseract"
            )

        import pytesseract
        from PIL import Image

        if isinstance(source, (str, Path)):
            path = Path(source)
            if not path.exists():
                raise FileNotFoundError(f"Image not found: {path}")
            img = Image.open(path)
        else:
            img = source  # Assume PIL Image

        # Pre-process for better OCR: convert to grayscale
        img = img.convert("L")

        text = pytesseract.image_to_string(img, lang=self.lang)
        return text

    def parse_chat_lines(self, text: str) -> list[dict]:
        """
        Parse raw OCR text into a list of conversation turns.

        Heuristics:
          - Lines matching "Name: message" are speaker turns
          - Lines that look like timestamps are skipped
          - Consecutive lines by the same speaker are merged

        Returns:
            List of {"speaker": str, "message": str} dicts.
        """
        lines = text.strip().splitlines()
        turns: list[dict] = []

        # Regex: "Speaker: message" — speaker is 1-30 chars, no colon
        speaker_re = re.compile(r"^([^:]{1,30}):\s+(.+)$")
        # Timestamp pattern (skip these)
        time_re = re.compile(r"^\d{1,2}:\d{2}(\s?[APap][Mm])?$")

        current_speaker: str | None = None
        current_lines: list[str] = []

        def flush() -> None:
            if current_speaker and current_lines:
                turns.append({
                    "speaker": current_speaker,
                    "message": " ".join(current_lines).strip(),
                })

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            if time_re.match(line):
                continue

            match = speaker_re.match(line)
            if match:
                flush()
                current_lines = []
                current_speaker = match.group(1).strip()
                msg = match.group(2).strip()
                if msg:
                    current_lines.append(msg)
            else:
                # Continuation line
                if current_speaker:
                    current_lines.append(line)
                else:
                    # Unknown speaker — tag as "Unknown"
                    turns.append({"speaker": "Unknown", "message": line})

        flush()
        return turns

    def extract_conversation(
        self,
        source: Union[str, Path, "PIL.Image.Image"],
    ) -> list[dict]:
        """
        Convenience: read image + parse in one call.

        Returns list of {"speaker": str, "message": str} dicts.
        """
        text = self.read_image(source)
        return self.parse_chat_lines(text)

    def turns_to_text(self, turns: list[dict]) -> str:
        """Format parsed turns as a plain text conversation string."""
        return "\n".join(f"{t['speaker']}: {t['message']}" for t in turns)

    @staticmethod
    def is_available() -> bool:
        """Return True if Tesseract OCR is installed and usable."""
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False
