"""APix collector v2 â€” three-tier escalation with captcha handling."""

from .captcha import detect_captcha
from .orchestrator import ProgressEvent, QuoteRow, append_quotes, run_collection
from .tiers import FetchResult, TierUnavailableError, fetch_with_escalation

__all__ = [
    "run_collection",
    "ProgressEvent",
    "QuoteRow",
    "append_quotes",
    "fetch_with_escalation",
    "FetchResult",
    "TierUnavailableError",
    "detect_captcha",
]
