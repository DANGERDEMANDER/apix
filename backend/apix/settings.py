"""Pydantic Settings. Loads the three YAML configs with field-named errors.

Rule 9: nothing hardcoded that an operator might change lives in code — it
lives in config/*.yaml. This module is the single reader of those files.

Design note: EnvSettings is a BaseSettings that reads environment variables.
Settings is a frozen Pydantic model that bundles EnvSettings with the parsed
YAML configs. The two are kept separate so that (a) mypy strict is happy
without type: ignore on required fields, and (b) tests can inject a
config_dir without polluting the environment-variable namespace.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

# ---------- config/*.yaml schemas ----------


class RouteConfig(BaseModel):
    """Route structure only. Weights are data, not config — see METHODOLOGY.md."""

    origin: str = Field(min_length=3, max_length=3)
    destination: str = Field(min_length=3, max_length=3)
    label: str

    @field_validator("origin", "destination")
    @classmethod
    def _upper_alpha3(cls, v: str) -> str:
        v = v.upper()
        if not v.isalpha() or len(v) != 3:
            raise ValueError("must be a 3-letter IATA code")
        return v


class BasketConfig(BaseModel):
    weight_period: str
    routes: list[RouteConfig] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_labels(self) -> BasketConfig:
        labels = [r.label for r in self.routes]
        if len(labels) != len(set(labels)):
            raise ValueError("route labels must be unique")
        return self


class SourceConfig(BaseModel):
    name: str
    kind: Literal["airline", "ota"]
    base_url: str
    rate_limit_rpm: int = Field(gt=0)
    crawl_delay_s: float = Field(ge=0)
    is_enabled: bool = False


class SourcesConfig(BaseModel):
    sources: list[SourceConfig] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_names(self) -> SourcesConfig:
        names = [s.name for s in self.sources]
        if len(names) != len(set(names)):
            raise ValueError("source names must be unique")
        return self


class IndexConfig(BaseModel):
    advance_windows_days: list[int] = Field(min_length=1)
    window_weights: dict[int, float]
    window_weights_source: Literal["prior", "calibrated"] = "prior"
    window_weights_prior: dict[int, float]
    calibration_metadata: dict[str, object] | None = None
    base_period_days: int = Field(gt=0)
    base_period_min_route_days: int = Field(gt=0)
    min_publishable_coverage: float = Field(gt=0, le=1)
    route_suspension_days: int = Field(ge=1)
    min_fare_inr: int = Field(gt=0)
    max_fare_inr: int = Field(gt=0)
    max_imputation_share: float = Field(gt=0, le=1)
    gst_rate_economy: float = Field(ge=0, le=1)
    udf_inr_per_airport: dict[str, int]

    @model_validator(mode="after")
    def _validate(self) -> IndexConfig:
        win = set(self.advance_windows_days)
        for name, weights in (
            ("window_weights", self.window_weights),
            ("window_weights_prior", self.window_weights_prior),
        ):
            if set(weights.keys()) != win:
                raise ValueError(
                    f"{name} keys {sorted(weights)} must match "
                    f"advance_windows_days {sorted(win)}"
                )
            total = sum(weights.values())
            if abs(total - 1.0) > 1e-9:
                raise ValueError(f"{name} must sum to 1.0, got {total!r}")
        if self.min_fare_inr >= self.max_fare_inr:
            raise ValueError("min_fare_inr must be < max_fare_inr")
        if self.window_weights_source == "calibrated" and self.calibration_metadata is None:
            raise ValueError(
                "window_weights_source is 'calibrated' but calibration_metadata is null"
            )
        return self


# ---------- process/env settings ----------


class EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APIX_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Literal["local", "docker", "ci"] = "local"
    db_url: str = "postgresql+asyncpg://apix:apix@localhost:5432/apix"
    config_dir: Path = Path("./config")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    cors_origin: str = "http://localhost:5173"
    collection_enabled: bool = False
    enable_live: bool = False


class Settings(BaseModel):
    """Frozen bundle of env settings + parsed YAML configs."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    env: EnvSettings
    basket: BasketConfig
    sources: SourcesConfig
    index: IndexConfig


# ---------- loader ----------


def _read_yaml(path: Path) -> object:
    if not path.is_file():
        raise FileNotFoundError(f"config file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _load_configs(config_dir: Path) -> Settings:
    try:
        basket = BasketConfig.model_validate(_read_yaml(config_dir / "basket.yaml"))
        sources = SourcesConfig.model_validate(_read_yaml(config_dir / "sources.yaml"))
        index = IndexConfig.model_validate(_read_yaml(config_dir / "index.yaml"))
    except ValidationError as exc:
        # Re-raise with the offending file named, per Rule 9.
        raise SystemExit(f"config validation failed under {config_dir}:\n{exc}") from exc
    return Settings(env=EnvSettings(), basket=basket, sources=sources, index=index)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return settings, loading YAML configs exactly once per process."""
    env = EnvSettings()
    return _load_configs(env.config_dir)


def reset_settings_cache() -> None:
    """Test-only hook to force a reload after env vars change."""
    get_settings.cache_clear()
