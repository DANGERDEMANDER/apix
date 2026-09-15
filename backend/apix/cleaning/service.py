"""DB wrapper around clean_quotes: read fare_quotes, write clean_fares."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from apix.cleaning.pipeline import FareRecord, RejectionReason, clean_quotes
from apix.models.clean import CleanFare
from apix.models.quotes import FareQuote


@dataclass(frozen=True)
class CleanReport:
    n_quotes_in: int
    n_accepted: int
    n_rejected: int
    by_reason: dict[str, int]


def _bounds(from_date: date, to_date: date) -> tuple[datetime, datetime]:
    start = datetime.combine(from_date, time(0, 0), tzinfo=timezone.utc)
    end = datetime.combine(to_date + timedelta(days=1), time(0, 0), tzinfo=timezone.utc)
    return start, end


async def run_cleaning(
    session: AsyncSession, from_date: date, to_date: date
) -> CleanReport:
    start, end = _bounds(from_date, to_date)
    stmt = select(FareQuote).where(
        FareQuote.collected_at >= start,
        FareQuote.collected_at < end,
    )
    quotes = list((await session.execute(stmt)).scalars().all())

    records = [
        FareRecord(
            quote_id=q.id,
            route_id=q.route_id,
            source_id=q.source_id,
            collection_date=q.collected_at.date(),
            departure_date=q.departure_date,
            advance_days=q.advance_days,
            carrier=q.carrier,
            base_fare=q.base_fare,
            taxes=q.taxes,
            udf=q.udf,
            convenience_fee=q.convenience_fee,
            total_fare=q.total_fare,
            is_sold_out=q.is_sold_out,
            decomposition_method=q.decomposition_method.value,
        )
        for q in quotes
    ]

    result = clean_quotes(records)

    await session.execute(
        delete(CleanFare).where(
            CleanFare.collection_date >= from_date,
            CleanFare.collection_date <= to_date,
        )
    )

    for row in result.accepted:
        session.add(
            CleanFare(
                quote_id=row.quote_id,
                route_id=row.route_id,
                source_id=row.source_id,
                collection_date=row.collection_date,
                advance_days=row.advance_days,
                base_fare=row.base_fare,
                total_fare=row.total_fare,
                is_outlier=row.is_outlier,
                outlier_reason=row.outlier_reason,
                is_imputed=row.is_imputed,
                imputation_method=row.imputation_method,
            )
        )
    await session.flush()

    counts = Counter(reason.value for _, reason in result.rejected)
    return CleanReport(
        n_quotes_in=len(records),
        n_accepted=len(result.accepted),
        n_rejected=len(result.rejected),
        by_reason=dict(counts),
    )
