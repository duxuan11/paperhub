"""CLI 配置与 HTTP 客户端。"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

CONFIG_DIR = Path(os.environ.get("PAPERHUB_CONFIG_DIR", Path.home() / ".paperhub"))
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_BASE_URL = os.environ.get("PAPERHUB_API_URL", "http://localhost:8000").rstrip(
    "/"
)


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_config(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))


def get_base_url() -> str:
    return load_config().get("base_url", DEFAULT_BASE_URL)


def get_api_key() -> str:
    return load_config().get("api_key", os.environ.get("PAPERHUB_API_KEY", ""))


def _headers() -> dict:
    h = {}
    key = get_api_key()
    if key:
        h["Authorization"] = f"Bearer {key}"
    return h


def client() -> httpx.Client:
    return httpx.Client(base_url=get_base_url(), headers=_headers(), timeout=120.0)
