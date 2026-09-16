"""Captcha detection and bypass.

Passive: Patchright's stealth handles most cases without solving anything.
Active: local OCR for image grids, or a paid solver API if enabled.
"""
from __future__ import annotations

import logging
import os
import re
from io import BytesIO
from typing import Optional

LOG = logging.getLogger("apix.collector.captcha")

CAPTCHA_MARKERS = [
    r"recaptcha",
    r"hcaptcha",
    r"cf-turnstile",
    r"g-recaptcha",
    r"are you a robot",
    r"verify you are human",
    r"unusual traffic",
]


def detect_captcha(html: str) -> Optional[str]:
    """Return the captcha vendor marker if the body looks like a challenge."""
    low = html.lower()
    for marker in CAPTCHA_MARKERS:
        if re.search(marker, low):
            return marker
    return None


async def solve_with_ocr(image_bytes: bytes) -> Optional[str]:
    """Local OCR for simple text captchas. Free, no API key."""
    try:
        import cv2
        import numpy as np
        from PIL import Image
        import pytesseract
    except ImportError:
        LOG.warning("ocr dependencies missing; skipping solve")
        return None

    img = Image.open(BytesIO(image_bytes)).convert("L")
    arr = np.array(img)
    _, thresh = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    text = pytesseract.image_to_string(thresh, config="--psm 7").strip()
    return text or None


async def solve_with_2captcha(sitekey: str, pageurl: str) -> Optional[str]:
    """Paid solver fallback. Only used if TWOCAPTCHA_KEY is set."""
    api_key = os.environ.get("TWOCAPTCHA_KEY")
    if not api_key:
        return None

    try:
        from twocaptcha import TwoCaptcha
    except ImportError:
        LOG.warning("2captcha-python not installed; skipping paid solve")
        return None

    solver = TwoCaptcha(api_key)
    try:
        result = solver.recaptcha(sitekey=sitekey, url=pageurl)
        return result.get("code")
    except Exception as e:
        LOG.error("2captcha failed: %s", e)
        return None
