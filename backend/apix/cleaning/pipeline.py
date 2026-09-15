"""Section 8 - the cleaning pipeline.

Five steps, applied in order:
  1. Structural validation
  2. Sold-out handling
  3. Fare decomposition (parsed / partial / modelled / none)
  4. Outlier detection (MAD per (route, window) + absolute guardrails)
  5. Imputation (stub for this batch; carried forward in Batch 3)
"""

from __future__ import annotations

import enum
import statistics
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal

from apix.settings import get_settings


class RejectionReason(str, enum.Enum):
    STRUCTURAL_ZERO_FARE = "structural_zero_fare"
    STRUCTURAL_MISSING_ROUTE = "structural_missing_route"
    STRUCTURAL_BAD_WINDOW = "structural_bad_window"
    STRUCTURAL_DEPARTURE_MISMATCH = "structural_departure_mismatch"
    SOLD_OUT = "sold_out"
    OUTLIER_MAD = "outlier_mad"
    OUTLIER_ABSOLUTE = "outlier_absolute"


@dataclass(frozen=True)
class FareRecord:
    quote_id: int
    route_id: int
    source_id: int
    collection_date: date
    departure_date: date
    advance_days: int
    carrier: str
    base_fare: Decimal | None
    taxes: Decimal | None
    udf: Decimal | None
    convenience_fee: Decimal | None
    total_fare: Decimal
    is_sold_out: bool
    decomposition_method: str


@dataclass(frozen=True)
class CleanRow:
    quote_id: int
    route_id: int
    source_id: int
    collection_date: date
    advance_days: int
    base_fare: Decimal
    total_fare: Decimal
    is_outlier: bool
    outlier_reason: str | None
    is_imputed: bool
    imputation_method: str | None


@dataclass(frozen=True)
class CleanResult:
    accepted: list[CleanRow]
    rejected: list[tuple[FareRecord, RejectionReason]]
    imputation_share: Decimal


def _structural(rec: FareRecord, valid_windows: set[int]) -> RejectionReason | None:
    if rec.total_fare <= 0:
        return RejectionReason.STRUCTURAL_ZERO_FARE
    if rec.route_id <= 0:
        return RejectionReason.STRUCTURAL_MISSING_ROUTE
    if rec.advance_days not in valid_windows:
        return RejectionReason.STRUCTURAL_BAD_WINDOW
    expected = rec.collection_date + timedelta(days=rec.advance_days)
    if rec.departure_date != expected:
        return RejectionReason.STRUCTURAL_DEPARTURE_MISMATCH
    return None


def _decompose(rec: FareRecord) -> FareRecord:
    if rec.base_fare is not None:
        return rec

    s = get_settings()
    if rec.decomposition_method == "parsed":
        taxes = rec.taxes or Decimal("0")
        udf = rec.udf or Decimal("0")
        conv = rec.convenience_fee or Decimal("0")
        return replace(rec, base_fare=rec.total_fare - taxes - udf - conv)

    gst = (rec.total_fare * Decimal(str(s.index.gst_rate_economy))).quantize(Decimal("0.01"))
    udf = Decimal(s.index.udf_inr_per_airport.get("DEL", 249))
    base = (rec.total_fare - gst - udf).quantize(Decimal("0.01"))
    if base < Decimal("0"):
        base = rec.total_fare
    return replace(rec, base_fare=base)


def _trailing_key(rec: FareRecord) -> tuple[int, int]:
    return (rec.route_id, rec.advance_days)


def _mark_outliers(records: list[FareRecord]) -> dict[int, RejectionReason]:
    s = get_settings()
    min_fare = Decimal(s.index.min_fare_inr)
    max_fare = Decimal(s.index.max_fare_inr)
    sigma_mult = Decimal("1.4826")
    threshold = Decimal("3.5")

    by_key: dict[tuple[int, int], list[FareRecord]] = defaultdict(list)
    for r in records:
        by_key[_trailing_key(r)].append(r)

    outliers: dict[int, RejectionReason] = {}
    for _, group in by_key.items():
        group_sorted = sorted(group, key=lambda r: r.collection_date)
        for i, rec in enumerate(group_sorted):
            bf = rec.base_fare
            assert bf is not None
            if bf < min_fare or bf > max_fare:
                outliers[rec.quote_id] = RejectionReason.OUTLIER_ABSOLUTE
                continue

            window_start = rec.collection_date - timedelta(days=30)
            window = [
                g.base_fare
                for g in group_sorted[: i + 1]
                if g.collection_date >= window_start and g.base_fare is not None
            ]
            if len(window) < 5:
                continue
            med = statistics.median(window)
            devs = [abs(float(x - med)) for x in window]
            mad = statistics.median(devs)
            if mad == 0:
                continue
            sigma = float(sigma_mult) * mad
            if abs(float(bf - med)) > float(threshold) * sigma:
                outliers[rec.quote_id] = RejectionReason.OUTLIER_MAD
    return outliers


def clean_quotes(records: list[FareRecord]) -> CleanResult:
    s = get_settings()
    valid_windows = set(s.index.advance_windows_days)

    rejected: list[tuple[FareRecord, RejectionReason]] = []
    stage1: list[FareRecord] = []
    for r in records:
        reason = _structural(r, valid_windows)
        if reason is not None:
            rejected.append((r, reason))
            continue
        if r.is_sold_out:
            rejected.append((r, RejectionReason.SOLD_OUT))
            continue
        stage1.append(r)

    decomposed = [_decompose(r) for r in stage1]
    outlier_map = _mark_outliers(decomposed)
    for r in decomposed:
        if r.quote_id in outlier_map:
            rejected.append((r, outlier_map[r.quote_id]))

    kept = [r for r in decomposed if r.quote_id not in outlier_map]

    accepted: list[CleanRow] = []
    for r in kept:
        assert r.base_fare is not None
        accepted.append(
            CleanRow(
                quote_id=r.quote_id,
                route_id=r.route_id,
                source_id=r.source_id,
                collection_date=r.collection_date,
                advance_days=r.advance_days,
                base_fare=r.base_fare.quantize(Decimal("0.01")),
                total_fare=r.total_fare.quantize(Decimal("0.01")),
                is_outlier=False,
                outlier_reason=None,
                is_imputed=False,
                imputation_method=None,
            )
        )

    return CleanResult(
        accepted=accepted,
        rejected=rejected,
        imputation_share=Decimal("0"),
    )
