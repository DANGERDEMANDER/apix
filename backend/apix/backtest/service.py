"""Compare monthly APIx against dgca_reference.

APIx is on index=100 scale; DGCA is on INR scale. To compare them, both are
re-based to 100 on the first month where both exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apix.backtest.metrics import BacktestMetrics, compute_metrics
from apix.models.dgca import DgcaReference
from apix.models.indices import Frequency, IndexStatus, IndexValue, Measure


@dataclass(frozen=True)
class BacktestRow:
    month: str
    apix_value: float
    dgca_value: float
    apix_pct_of_base: float
    dgca_pct_of_base: float


@dataclass(frozen=True)
class BacktestResult:
    rows: list[BacktestRow]
    metrics: BacktestMetrics
    provenance_note: str


async def run_backtest(session: AsyncSession) -> BacktestResult:
    # Load monthly APix (base measure) with published status.
    idx_stmt = (
        select(IndexValue)
        .where(
            IndexValue.frequency == Frequency.MONTHLY,
            IndexValue.measure == Measure.BASE,
            IndexValue.status == IndexStatus.PUBLISHED,
        )
        .order_by(IndexValue.date)
    )
    index_rows = list((await session.execute(idx_stmt)).scalars().all())

    # Load DGCA reference.
    ref_stmt = select(DgcaReference).order_by(DgcaReference.month)
    ref_rows = list((await session.execute(ref_stmt)).scalars().all())

    # Build {month: mean_apix} and {month: mean_dgca_fare}.
    # We group by calendar month and average across routes if multiple rows.
    apix_by_month: dict[tuple[int, int], list[Decimal]] = {}
    for iv in index_rows:
        if iv.value is None:
            continue
        apix_by_month.setdefault((iv.date.year, iv.date.month), []).append(iv.value)

    dgca_by_month: dict[tuple[int, int], list[Decimal]] = {}
    for dr in ref_rows:
        dgca_by_month.setdefault((dr.month.year, dr.month.month), []).append(dr.avg_fare)

    common_months = sorted(set(apix_by_month.keys()) & set(dgca_by_month.keys()))
    if not common_months:
        return BacktestResult(
            rows=[],
            metrics=compute_metrics([], []),
            provenance_note=(
                "No overlapping months between published monthly APix and "
                "dgca_reference. Run `apix seed` (to load the reference CSV), "
                "`apix index` (to compute monthly values), then retry."
            ),
        )

    apix_means = [
        float(sum(apix_by_month[m], start=Decimal("0")) / Decimal(len(apix_by_month[m])))
        for m in common_months
    ]
    dgca_means = [
        float(sum(dgca_by_month[m], start=Decimal("0")) / Decimal(len(dgca_by_month[m])))
        for m in common_months
    ]

    # Rebase both to 100 on the first common month.
    apix_base = apix_means[0]
    dgca_base = dgca_means[0]
    apix_indexed = [100.0 * v / apix_base for v in apix_means] if apix_base else apix_means
    dgca_indexed = [100.0 * v / dgca_base for v in dgca_means] if dgca_base else dgca_means

    rows = [
        BacktestRow(
            month=f"{y:04d}-{mo:02d}",
            apix_value=round(a, 4),
            dgca_value=round(d, 2),
            apix_pct_of_base=round(ai, 4),
            dgca_pct_of_base=round(di, 4),
        )
        for (y, mo), a, d, ai, di in zip(
            common_months, apix_means, dgca_means, apix_indexed, dgca_indexed, strict=True
        )
    ]

    metrics = compute_metrics(apix_indexed, dgca_indexed)

    note_parts = [
        f"{len(ref_rows)} DGCA reference rows across {len(dgca_by_month)} months.",
        "Source tags in dgca_reference.source_note indicate provenance: "
        "values tagged SYNTHETIC are placeholders pending real DGCA data.",
    ]
    provenance_note = " ".join(note_parts)

    return BacktestResult(rows=rows, metrics=metrics, provenance_note=provenance_note)
