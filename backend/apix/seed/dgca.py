"""Load data/dgca/reference.csv into dgca_reference. No-op if file absent."""

from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from apix.models.dgca import DgcaReference
from apix.models.routes import Route

_REFERENCE_CSV = Path("data/dgca/reference.csv")


async def seed_dgca_reference(session: AsyncSession) -> int:
    if not _REFERENCE_CSV.is_file():
        return 0

    routes = {
        r.label: r for r in (await session.execute(select(Route))).scalars().all()
    }

    # Clear and reload to keep the table a faithful mirror of the CSV.
    await session.execute(delete(DgcaReference))

    written = 0
    with _REFERENCE_CSV.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            label = row["label"].strip()
            month = date.fromisoformat(row["month"].strip())
            avg_fare = Decimal(row["avg_fare"].strip())
            note = row.get("source_note", "").strip() or "synthetic placeholder"

            route = routes.get(label)
            if route is None:
                raise ValueError(f"dgca_reference row references unknown route {label}")

            session.add(
                DgcaReference(
                    month=month,
                    route_id=route.id,
                    avg_fare=avg_fare,
                    source_note=note,
                )
            )
            written += 1

    await session.flush()
    return written
