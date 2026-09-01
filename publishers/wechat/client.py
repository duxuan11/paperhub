"""微信公众号 API 客户端。

只实现 MVP 必需的能力：获取 access_token、创建草稿（draft/add）、发布草稿。
安全设计：默认只创建草稿，不直接发布。
"""

from __future__ import annotations

import time

import httpx


class WeChatClient:
    BASE = "https://api.weixin.qq.com"

    def __init__(self, app_id: str, app_secret: str) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self._token: str | None = None
        self._token_expires: float = 0.0

    async def get_access_token(self) -> str:
        if self._token and time.time() < self._token_expires - 60:
            return self._token
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.BASE}/cgi-bin/token",
                params={
                    "grant_type": "client_credential",
                    "appid": self.app_id,
                    "secret": self.app_secret,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if "access_token" not in data:
                raise RuntimeError(f"获取 access_token 失败: {data}")
            self._token = data["access_token"]
            self._token_expires = time.time() + int(data.get("expires_in", 7200))
            assert self._token is not None
            return self._token

    async def add_draft(self, articles: list[dict]) -> dict:
        """articles: 图文消息列表（公众号要求 1-8 篇）。"""
        token = await self.get_access_token()
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.BASE}/cgi-bin/draft/add",
                params={"access_token": token},
                json={"articles": articles},
            )
            resp.raise_for_status()
            return resp.json()

    async def publish(self, media_id: str) -> dict:
        """正式发布（需公众号发布权限）。"""
        token = await self.get_access_token()
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.BASE}/cgi-bin/freepublish/submit",
                params={"access_token": token},
                json={"media_id": media_id},
            )
            resp.raise_for_status()
            return resp.json()
