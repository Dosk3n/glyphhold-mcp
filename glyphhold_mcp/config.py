from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    glyphhold_url: str
    api_key: str
    timeout_seconds: float = 20.0


def load_settings() -> Settings:
    load_dotenv(Path.cwd() / ".env")

    glyphhold_url = os.getenv("GLYPHHOLD_URL", "").strip()
    api_key = os.getenv("GLYPHHOLD_API_KEY", "").strip()
    timeout = float(os.getenv("GLYPHHOLD_TIMEOUT_SECONDS", "20"))

    if not glyphhold_url:
        raise RuntimeError("GLYPHHOLD_URL is required.")
    if not api_key:
        raise RuntimeError("GLYPHHOLD_API_KEY is required.")

    return Settings(
        glyphhold_url=glyphhold_url.rstrip("/"),
        api_key=api_key,
        timeout_seconds=timeout,
    )
