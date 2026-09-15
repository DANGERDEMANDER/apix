"""Initial schema — routes, sources, runs, quotes, clean_fares,
daily_route_price, index_values, index_base_values, dgca_reference.

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    weight_source_enum = sa.Enum(
        "dgca-published", "dgca-synthetic", name="weight_source_enum"
    )
    source_kind_enum = sa.Enum("airline", "ota", name="source_kind_enum")
    run_mode_enum = sa.Enum("live", "replay", "synthetic", name="run_mode_enum")
    run_status_enum = sa.Enum(
        "running", "success", "partial", "failed", name="run_status_enum"
    )
    decomposition_method_enum = sa.Enum(
        "parsed", "partial", "modelled", "none", name="decomposition_method_enum"
    )
    frequency_enum = sa.Enum("daily", "weekly", "monthly", name="frequency_enum")
    measure_enum = sa.Enum("base", "total", name="measure_enum")
    index_status_enum = sa.Enum(
        "published", "insufficient_coverage", "no_data", name="index_status_enum"
    )

    op.create_table(
        "routes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("origin_iata", sa.String(3), nullable=False),
        sa.Column("destination_iata", sa.String(3), nullable=False),
        sa.Column("label", sa.String(16), nullable=False, unique=True),
        sa.Column("dgca_pax_annual", sa.Integer(), nullable=False),
        sa.Column("weight", sa.Numeric(8, 6), nullable=False),
        sa.Column("weight_period", sa.String(16), nullable=False),
        sa.Column("weight_source", weight_source_enum, nullable=False),
        sa.Column("weight_source_note", sa.String(256), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "origin_iata", "destination_iata", name="uq_routes_origin_dest"
        ),
    )

    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        sa.Column("kind", source_kind_enum, nullable=False),
        sa.Column("base_url", sa.String(256), nullable=False),
        sa.Column("rate_limit_rpm", sa.Integer(), nullable=False),
        sa.Column("crawl_delay_s", sa.Numeric(4, 1), nullable=False),
        sa.Column("robots_last_checked", sa.DateTime(timezone=True), nullable=True),
        sa.Column("robots_allows_target", sa.Boolean(), nullable=True),
        sa.Column(
            "is_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "collection_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mode", run_mode_enum, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", run_status_enum, nullable=False),
        sa.Column(
            "quotes_collected", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "quotes_expected", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "blocked_sources",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "error_summary",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("seed", sa.BigInteger(), nullable=True),
        sa.Column("notes", sa.String(512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "fare_quotes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("collection_runs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "route_id",
            sa.Integer(),
            sa.ForeignKey("routes.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "source_id",
            sa.Integer(),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("departure_date", sa.Date(), nullable=False),
        sa.Column("advance_days", sa.SmallInteger(), nullable=False),
        sa.Column("carrier", sa.CHAR(2), nullable=False),
        sa.Column("flight_number", sa.String(16), nullable=False),
        sa.Column("fare_class", sa.String(32), nullable=False),
        sa.Column("base_fare", sa.Numeric(10, 2), nullable=True),
        sa.Column("taxes", sa.Numeric(10, 2), nullable=True),
        sa.Column("udf", sa.Numeric(10, 2), nullable=True),
        sa.Column("convenience_fee", sa.Numeric(10, 2), nullable=True),
        sa.Column("total_fare", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False, server_default="INR"),
        sa.Column(
            "is_sold_out", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("decomposition_method", decomposition_method_enum, nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_fare_quotes_route_dep_window",
        "fare_quotes",
        ["route_id", "departure_date", "advance_days"],
    )

    op.create_table(
        "clean_fares",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "quote_id",
            sa.Integer(),
            sa.ForeignKey("fare_quotes.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "route_id",
            sa.Integer(),
            sa.ForeignKey("routes.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "source_id",
            sa.Integer(),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("collection_date", sa.Date(), nullable=False, index=True),
        sa.Column("advance_days", sa.SmallInteger(), nullable=False),
        sa.Column("base_fare", sa.Numeric(10, 2), nullable=False),
        sa.Column("total_fare", sa.Numeric(10, 2), nullable=False),
        sa.Column(
            "is_outlier", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("outlier_reason", sa.String(128), nullable=True),
        sa.Column(
            "is_imputed", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("imputation_method", sa.String(32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("quote_id", name="uq_clean_fares_quote_id"),
    )

    op.create_table(
        "daily_route_price",
        sa.Column("date", sa.Date(), primary_key=True),
        sa.Column(
            "route_id",
            sa.Integer(),
            sa.ForeignKey("routes.id", ondelete="RESTRICT"),
            primary_key=True,
            index=True,
        ),
        sa.Column("avg_base_fare", sa.Numeric(10, 2), nullable=False),
        sa.Column("avg_total_fare", sa.Numeric(10, 2), nullable=False),
        sa.Column("n_quotes", sa.Integer(), nullable=False),
        sa.Column("n_windows_present", sa.SmallInteger(), nullable=False),
        sa.Column("coverage_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "index_values",
        sa.Column("date", sa.Date(), primary_key=True),
        sa.Column("frequency", frequency_enum, primary_key=True),
        sa.Column("measure", measure_enum, primary_key=True),
        sa.Column("value", sa.Numeric(10, 4), nullable=True),
        sa.Column("base_period", sa.String(64), nullable=False),
        sa.Column("routes_included", sa.SmallInteger(), nullable=False),
        sa.Column("weight_covered", sa.Numeric(8, 6), nullable=False),
        sa.Column(
            "contributions",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("status", index_status_enum, nullable=False),
        sa.Column("withheld_reason", sa.String(128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "index_base_values",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "route_id",
            sa.Integer(),
            sa.ForeignKey("routes.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("measure", measure_enum, nullable=False),
        sa.Column("base_period", sa.String(64), nullable=False),
        sa.Column("p_i0", sa.Numeric(10, 4), nullable=False),
        sa.Column("n_base_days", sa.SmallInteger(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "dgca_reference",
        sa.Column("month", sa.Date(), primary_key=True),
        sa.Column(
            "route_id",
            sa.Integer(),
            sa.ForeignKey("routes.id", ondelete="RESTRICT"),
            primary_key=True,
            index=True,
        ),
        sa.Column("avg_fare", sa.Numeric(10, 2), nullable=False),
        sa.Column("source_note", sa.String(512), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("dgca_reference")
    op.drop_table("index_base_values")
    op.drop_table("index_values")
    op.drop_table("daily_route_price")
    op.drop_table("clean_fares")
    op.drop_index("ix_fare_quotes_route_dep_window", table_name="fare_quotes")
    op.drop_table("fare_quotes")
    op.drop_table("collection_runs")
    op.drop_table("sources")
    op.drop_table("routes")

    sa.Enum(name="index_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="measure_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="frequency_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="decomposition_method_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="run_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="run_mode_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="source_kind_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="weight_source_enum").drop(op.get_bind(), checkfirst=True)