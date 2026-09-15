"""Load config/sources.yaml into the sources table. Idempotent."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apix.models.sources import Source, SourceKind
from apix.settings import get_settings


async def seed_sources(session: AsyncSession) -> int:
    settings = get_settings()

    existing = {
        s.name: s for s in (await session.execute(select(Source))).scalars().all()
    }

    written = 0
    for s in settings.sources.sources:
        kind = SourceKind.AIRLINE if s.kind == "airline" else SourceKind.OTA
        row = existing.get(s.name)
        if row is None:
            row = Source(
                name=s.name,
                kind=kind,
                base_url=s.base_url,
                rate_limit_rpm=s.rate_limit_rpm,
                crawl_delay_s=Decimal(str(s.crawl_delay_s)),
                is_enabled=s.is_enabled,
            )
            session.add(row)
        else:
            row.kind = kind
            row.base_url = s.base_url
            row.rate_limit_rpm = s.rate_limit_rpm
            row.crawl_delay_s = Decimal(str(s.crawl_delay_s))
            row.is_enabled = s.is_enabled
        written += 1

    await session.flush()
    return written