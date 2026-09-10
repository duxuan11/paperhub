"""微信公众号 API 客户端。

只实现 MVP 必需的能力：获取 access_token、上传正文图片、上传封面永久素材、
创建草稿（draft/add）、发布草稿（freepublish/submit）。

安全设计：默认只创建草稿，不直接发布。

注意：微信接口在业务失败时仍返回 HTTP 200，错误信息在响应体的 errcode/errmsg 中。
因此所有响应都必须经过 _check()，否则失败会被静默当成成功。
"""

from __future__ import annotations

import time
from typing import Any

import httpx

# 常见 errcode 的可操作提示
ERROR_HINTS: dict[int, str] = {
    40001: "access_token 无效（app_secret 错误，或 token 被其它服务刷新过）",
    40007: "media_id 非法：封面图 thumb_media_id 必须是有效的「永久素材」ID",
    40013: "appid 无效，请核对 WECHAT_APP_ID",
    40164: (
        "调用方 IP 不在公众号 IP 白名单：请到 公众号后台 → 设置与开发 → 基本配置 → "
        "IP白名单 里加入该出口 IP 后重试"
    ),
    41001: "缺少 access_token 参数",
    45009: "接口调用超过限额（公众号每日调用量受限）",
    48001: "接口未授权：当前公众号类型 / 未认证账号不支持该接口",
    53503: "草稿箱功能未开启，请在公众号后台开启后再试",
    53504: "发布功能未开启，请在公众号后台开启后再试",
}


class WeChatAPIError(RuntimeError):
    """微信接口业务错误（HTTP 200 但 errcode != 0）。"""

    def __init__(self, api: str, errcode: int | None, errmsg: str) -> None:
        self.api = api
        self.errcode = errcode
        self.errmsg = errmsg
        super().__init__(self._message())

    def _message(self) -> str:
        msg = f"微信接口 {self.api} 失败: errcode={self.errcode} errmsg={self.errmsg}"
        hint = ERROR_HINTS.get(self.errcode) if self.errcode else None
        if hint:
            msg += f"（提示：{hint}）"
        return msg


def _check(api: str, data: Any) -> dict:
    """校验微信响应体，errcode 非 0 时抛出带提示的异常。"""
    if not isinstance(data, dict):
        raise WeChatAPIError(api, None, f"响应格式异常: {data!r}")
    errcode = data.get("errcode")
    if errcode not in (0, None):
        raise WeChatAPIError(api, errcode, str(data.get("errmsg") or data))
    return data


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
            data = _check("cgi-bin/token", resp.json())
            token = data.get("access_token")
            if not token:
                raise WeChatAPIError("cgi-bin/token", None, f"响应缺少 access_token: {data}")
            self._token = token
            self._token_expires = time.time() + int(data.get("expires_in", 7200))
            return token

    async def add_draft(self, articles: list[dict]) -> dict:
        """articles: 图文消息列表（公众号要求 1-8 篇）。返回 {media_id: ...}。"""
        token = await self.get_access_token()
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.BASE}/cgi-bin/draft/add",
                params={"access_token": token},
                json={"articles": articles},
            )
            resp.raise_for_status()
            return _check("cgi-bin/draft/add", resp.json())

    async def publish(self, media_id: str) -> dict:
        """正式发布草稿（需公众号发布权限）。返回 {publish_id: ...}。"""
        token = await self.get_access_token()
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.BASE}/cgi-bin/freepublish/submit",
                params={"access_token": token},
                json={"media_id": media_id},
            )
            resp.raise_for_status()
            return _check("cgi-bin/freepublish/submit", resp.json())

    async def upload_content_image(self, data: bytes, filename: str) -> str:
        """上传正文内的图片，返回可在 content 中直接使用的 mmbiz URL。

        对应接口 /cgi-bin/media/uploadimg；正文图片必须换成该接口返回的 URL，
        否则微信侧不显示（本地/MinIO 地址微信无法访问）。
        """
        token = await self.get_access_token()
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.BASE}/cgi-bin/media/uploadimg",
                params={"access_token": token},
                files={"media": (filename, data)},
            )
            resp.raise_for_status()
            payload = _check("cgi-bin/media/uploadimg", resp.json())
        url = payload.get("url")
        if not url:
            raise WeChatAPIError("cgi-bin/media/uploadimg", None, f"响应缺少 url: {payload}")
        return str(url)

    async def upload_permanent_image(self, data: bytes, filename: str) -> str:
        """上传永久图片素材，返回 media_id（用于草稿封面 thumb_media_id）。"""
        token = await self.get_access_token()
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.BASE}/cgi-bin/material/add_material",
                params={"access_token": token, "type": "image"},
                files={"media": (filename, data)},
            )
            resp.raise_for_status()
            payload = _check("cgi-bin/material/add_material", resp.json())
        media_id = payload.get("media_id")
        if not media_id:
            raise WeChatAPIError(
                "cgi-bin/material/add_material", None, f"响应缺少 media_id: {payload}"
            )
        return str(media_id)
