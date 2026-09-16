"""Captcha detection and bypass.

Optional dependencies (cv2, pytesseract, PIL, 2captcha) are loaded via
importlib so mypy doesn't fail on missing stubs.
"""

from __future__ import annotations

import importlib
import logging
import os
import re
from typing import Any

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


def detect_captcha(html: str) -> str | None:
    """Return the captcha vendor marker if the body looks like a challenge."""
    low = html.lower()
    for marker in CAPTCHA_MARKERS:
        if re.search(marker, low):
            return marker
    return None


def _try_import(name: str) -> Any | None:
    try:
        return importlib.import_module(name)
    except ImportError:
        return None


async def solve_with_ocr(image_bytes: bytes) -> str | None:
    """Local OCR for simple text captchas. Free, no API key."""
    cv2 = _try_import("cv2")
    np = _try_import("numpy")
    pil_image = _try_import("PIL.Image")
    pytesseract = _try_import("pytesseract")

    if cv2 is None or np is None or pil_image is None or pytesseract is None:
        LOG.warning("ocr dependencies missing; skipping solve")
        return None

    from io import BytesIO

    img = pil_image.open(BytesIO(image_bytes)).convert("L")
    arr = np.array(img)
    _, thresh = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    text = pytesseract.image_to_string(thresh, config="--psm 7").strip()
    return text or None


async def solve_with_2captcha(sitekey: str, pageurl: str) -> str | None:
    """Paid solver fallback. Only used if TWOCAPTCHA_KEY is set."""
    api_key = os.environ.get("TWOCAPTCHA_KEY")
    if not api_key:
        return None

    twocaptcha = _try_import("twocaptcha")
    if twocaptcha is None:
        LOG.warning("2captcha-python not installed; skipping paid solve")
        return None

    solver = twocaptcha.TwoCaptcha(api_key)
    try:
        result = solver.recaptcha(sitekey=sitekey, url=pageurl)
        code = result.get("code") if isinstance(result, dict) else None
        return str(code) if code is not None else None
    except Exception as e:
        LOG.error("2captcha failed: %s", e)
        return None
