"""默认封面图生成（纯 Python，无 Pillow 依赖）。

微信草稿（article_type=news）要求 thumb_media_id 必填，即"封面图片素材id"。
文章没有任何配图时，用这里生成的渐变封面顶上，避免 draft/add 直接报 40007。
"""

from __future__ import annotations

import struct
import zlib

# 微信公众号封面推荐比例 2.35:1
COVER_WIDTH = 900
COVER_HEIGHT = 383
COVER_TOP = (15, 23, 42)  # 深蓝
COVER_BOTTOM = (37, 99, 235)  # 亮蓝


def _png(width: int, height: int, rows: list[bytes]) -> bytes:
    """把 RGB 行数据编码为 PNG（8-bit truecolor）。"""
    raw = b"".join(b"\x00" + row for row in rows)

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return (
            struct.pack(">I", len(data))
            + body
            + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def default_cover_png(
    width: int = COVER_WIDTH, height: int = COVER_HEIGHT
) -> bytes:
    """生成一张纵向渐变封面 PNG。"""
    rows: list[bytes] = []
    span = max(height - 1, 1)
    for y in range(height):
        t = y / span
        pixel = bytes(
            round(COVER_TOP[i] + (COVER_BOTTOM[i] - COVER_TOP[i]) * t) for i in range(3)
        )
        rows.append(pixel * width)
    return _png(width, height, rows)
