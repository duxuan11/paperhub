"""PaperHub REST API 客户端（供 MCP Server 使用）。"""

from __future__ import annotations

import os

import httpx

BASE_URL = os.environ.get("PAPERHUB_API_URL", "http://localhost:8000").rstrip("/")
API_KEY = os.environ.get("PAPERHUB_API_KEY", "")


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if API_KEY:
        h["Authorization"] = f"Bearer {API_KEY}"
    return h


def get(path: str, **params):
    r = httpx.get(f"{BASE_URL}{path}", params=params, headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


def post(path: str, json: dict | None = None):
    r = httpx.post(f"{BASE_URL}{path}", json=json, headers=_headers(), timeout=120)
    r.raise_for_status()
    return r.json()


def get_bytes(path: str) -> bytes:
    r = httpx.get(f"{BASE_URL}{path}", headers=_headers(), timeout=60)
    r.raise_for_status()
    return r.content
