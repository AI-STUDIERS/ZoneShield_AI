"""ZoneShield AI backend configuration.

All values overridable via environment variables prefixed with ZONESHIELD_.
Loaded from zoneshield.yaml at project root, then environment overrides.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable overrides."""

    # App
    env: str = Field(default="dev", alias="ZONESHIELD_ENV")
    debug: bool = Field(default=False, alias="ZONESHIELD_DEBUG")

    # Agent mode: mock | bedrock
    agent_mode: str = Field(default="mock", alias="ZONESHIELD_AGENT_MODE")
    bedrock_model_id: Optional[str] = Field(default=None, alias="ZONESHIELD_BEDROCK_MODEL_ID")
    aws_region: str = Field(default="us-east-1", alias="ZONESHIELD_AWS_REGION")

    # Database
    db_backend: str = Field(default="sqlite", alias="ZONESHIELD_DB_BACKEND")
    db_path: str = Field(default="data/zoneshield.db", alias="ZONESHIELD_DB_PATH")

    # Storage
    evidence_path: str = Field(default="data/evidence", alias="ZONESHIELD_EVIDENCE_PATH")

    # Vision
    opencv_major_required: int = Field(default=5, alias="ZONESHIELD_OPENCV_MAJOR_REQUIRED")
    num_threads: int = Field(default=4, alias="ZONESHIELD_NUM_THREADS")
    fps_target: int = Field(default=30, alias="ZONESHIELD_FPS_TARGET")

    # Cost guard
    idle_stop_minutes: int = Field(default=30, alias="ZONESHIELD_IDLE_STOP_MINUTES")
    max_daily_usd: float = Field(default=10.0, alias="ZONESHIELD_MAX_DAILY_USD")

    # Logging
    log_level: str = Field(default="INFO", alias="ZONESHIELD_LOG_LEVEL")

    model_config = {
        "populate_by_name": True,
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


def load_yaml_config(path: str | Path = "zoneshield.yaml") -> dict:
    """Load zoneshield.yaml if present, return dict (may be empty)."""
    p = Path(path)
    if not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


settings = Settings()