"""APix collector v2 — three-tier escalation with captcha handling."""
from .orchestrator import run_collection, ProgressEvent, QuoteRow, append_quotes
from .tiers import fetch_with_escalation, FetchResult, TierUnavailable
from .captcha import detect_captcha

__all__ = [
    "run_collection",
    "ProgressEvent",
    "QuoteRow",
    "append_quotes",
    "fetch_with_escalation",
    "FetchResult",
    "TierUnavailable",
    "detect_captcha",
]
