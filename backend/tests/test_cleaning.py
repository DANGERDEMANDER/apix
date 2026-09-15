"""Phase 4 acceptance tests for the cleaning pipeline.

Each test exercises one rejection reason or one decomposition rule.
Values are chosen to match the spec section 13 acceptance criteria
("injected outliers (a 99 fare and a 2,00,000 fare) are rejected with
the correct reason").
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from apix.cleaning.pipeline import (
    FareRecord,
    RejectionReason,
    clean_quotes,
)


def _make_record(
    *,
    quote_id: int = 1,
    route_id: int = 1,
    source_id: int = 1,
    collection_date: date = date(2025, 9, 1),
    advance_days: int = 15,
    base_fare: Decimal | None = None,
    taxes: Decimal | None = None,
    udf: Decimal | None = None,
    convenience_fee: Decimal | None = None,
    total_fare: Decimal = Decimal("5000.00"),
    is_sold_out: bool = False,
    decomposition_method: str = "parsed",
) -> FareRecord:
    return FareRecord(
        quote_id=quote_id,
        route_id=route_id,
        source_id=source_id,
        collection_date=collection_date,
        departure_date=collection_date + timedelta(days=advance_days),
        advance_days=advance_days,
        carrier="6E",
        base_fare=base_fare,
        taxes=taxes,
        udf=udf,
        convenience_fee=convenience_fee,
        total_fare=total_fare,
        is_sold_out=is_sold_out,
        decomposition_method=decomposition_method,
    )


def test_structural_zero_fare_rejected() -> None:
    r = _make_record(total_fare=Decimal("0.00"))
    res = clean_quotes([r])
    assert res.accepted == []
    assert res.rejected[0][1] == RejectionReason.STRUCTURAL_ZERO_FARE


def test_structural_bad_window_rejected() -> None:
    r = _make_record(advance_days=3)  # 3 is not in {1, 7, 15, 30, 45}
    res = clean_quotes([r])
    assert res.accepted == []
    assert res.rejected[0][1] == RejectionReason.STRUCTURAL_BAD_WINDOW


def test_structural_departure_mismatch_rejected() -> None:
    r = _make_record(advance_days=15)
    # Force a mismatch by building a FareRecord directly.
    bad = FareRecord(
        quote_id=r.quote_id,
        route_id=r.route_id,
        source_id=r.source_id,
        collection_date=r.collection_date,
        departure_date=r.collection_date + timedelta(days=7),  # wrong
        advance_days=15,
        carrier=r.carrier,
        base_fare=None,
        taxes=None,
        udf=None,
        convenience_fee=None,
        total_fare=r.total_fare,
        is_sold_out=False,
        decomposition_method="parsed",
    )
    res = clean_quotes([bad])
    assert res.accepted == []
    assert res.rejected[0][1] == RejectionReason.STRUCTURAL_DEPARTURE_MISMATCH


def test_sold_out_excluded_from_accepted() -> None:
    r = _make_record(is_sold_out=True)
    res = clean_quotes([r])
    assert res.accepted == []
    assert res.rejected[0][1] == RejectionReason.SOLD_OUT


def test_parsed_decomposition_backs_out_base() -> None:
    r = _make_record(
        base_fare=None,
        taxes=Decimal("249.00"),
        total_fare=Decimal("5000.00"),
        decomposition_method="parsed",
    )
    res = clean_quotes([r])
    assert len(res.accepted) == 1
    assert res.accepted[0].base_fare == Decimal("4751.00")


def test_modelled_decomposition_applies_gst_and_udf() -> None:
    r = _make_record(
        base_fare=None,
        taxes=None,
        udf=None,
        convenience_fee=None,
        total_fare=Decimal("5300.00"),
        decomposition_method="modelled",
    )
    res = clean_quotes([r])
    assert len(res.accepted) == 1
    # GST 5% = 265, UDF DEL = 249; base = 5300 - 265 - 249 = 4786
    assert res.accepted[0].base_fare == Decimal("4786.00")


def test_absolute_guardrail_low_rejected() -> None:
    """A 99 fare is below min_fare_inr=800 => OUTLIER_ABSOLUTE."""
    r = _make_record(
        base_fare=Decimal("99.00"),
        total_fare=Decimal("99.00"),
    )
    res = clean_quotes([r])
    assert res.accepted == []
    assert res.rejected[0][1] == RejectionReason.OUTLIER_ABSOLUTE


def test_absolute_guardrail_high_rejected() -> None:
    """A 2,00,000 fare is above max_fare_inr=90000 => OUTLIER_ABSOLUTE."""
    r = _make_record(
        base_fare=Decimal("200000.00"),
        total_fare=Decimal("200000.00"),
    )
    res = clean_quotes([r])
    assert res.accepted == []
    assert res.rejected[0][1] == RejectionReason.OUTLIER_ABSOLUTE


def test_normal_fare_passes_cleanly() -> None:
    r = _make_record(
        base_fare=Decimal("4500.00"),
        total_fare=Decimal("5000.00"),
    )
    res = clean_quotes([r])
    assert len(res.accepted) == 1
    assert res.accepted[0].base_fare == Decimal("4500.00")
    assert res.accepted[0].is_outlier is False
    assert res.accepted[0].is_imputed is False


def test_mixed_batch() -> None:
    """One valid, one sold-out, one zero-fare, one below guardrail."""
    good = _make_record(quote_id=1, base_fare=Decimal("4500.00"), total_fare=Decimal("5000.00"))
    sold = _make_record(quote_id=2, is_sold_out=True)
    zero = _make_record(quote_id=3, total_fare=Decimal("0.00"))
    cheap = _make_record(quote_id=4, base_fare=Decimal("50.00"), total_fare=Decimal("50.00"))
    res = clean_quotes([good, sold, zero, cheap])
    assert len(res.accepted) == 1
    assert res.accepted[0].quote_id == 1
    assert len(res.rejected) == 3
    reasons = {r[0].quote_id: r[1] for r in res.rejected}
    assert reasons[2] == RejectionReason.SOLD_OUT
    assert reasons[3] == RejectionReason.STRUCTURAL_ZERO_FARE
    assert reasons[4] == RejectionReason.OUTLIER_ABSOLUTE
