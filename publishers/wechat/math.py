"""公式提取 / 归一化 / 渲染（微信发布用）。

微信公众号正文无法加载 KaTeX 的 CSS / 字体，因此发布链路把 `$...$`
公式渲染成 PNG，再走 ``media/uploadimg`` 换成 mmbiz URL 插入正文。

matplotlib 只在真正渲染时惰性 import，便于测试与启动提速。
"""

from __future__ import annotations

import io
import re

# 行内公式：$...$，起始 $ 后不能是空白，结束 $ 前不能是空白，内容不含换行 / 反引号 / $
# 负向环视排除 $$ 与转义 \$
INLINE_MATH_RE = re.compile(
    r"(?<![\\$])\$(?![\s$])(?P<inline>[^$\n`]+?)(?<![\s\\])(?<![\\$])\$"
)
# 块级公式：$$...$$（可跨行）
DISPLAY_MATH_RE = re.compile(r"\$\$(?P<display>.+?)\$\$", re.S)
# 提取公式前先屏蔽代码，避免把代码里的 $ 当公式
_INLINE_CODE_RE = re.compile(r"`[^`]*`")
_FENCE_RE = re.compile(r"```.*?```", re.S)
# 一个正则里同时匹配块级与行内，保证按出现顺序提取
_MATH_RE = re.compile(
    DISPLAY_MATH_RE.pattern + "|" + INLINE_MATH_RE.pattern, re.S
)

# matplotlib mathtext 的宏名与 LaTeX 常用写法不同，先归一化
_NORMALIZE: dict[str, str] = {
    r"\ge": r"\geq",
    r"\le": r"\leq",
    r"\ne": r"\neq",
    r"\to": r"\rightarrow",
    r"\gets": r"\leftarrow",
    r"\land": r"\wedge",
    r"\lor": r"\vee",
}
_MACRO_BOUNDARY = r"(?![A-Za-z])"


def normalize_tex(tex: str) -> str:
    """把 LaTeX 常用宏名归一化成 matplotlib mathtext 认识的名字。"""
    out = tex
    for src, dst in _NORMALIZE.items():
        # 用函数替换：dst 里的 ``\g`` / ``\l`` 等若当模板会被 re 当作组引用
        out = re.sub(re.escape(src) + _MACRO_BOUNDARY, lambda _m, _d=dst: _d, out)
    return out


def _strip_code(md: str) -> str:
    return _INLINE_CODE_RE.sub(" ", _FENCE_RE.sub(" ", md))


def extract_math(md: str) -> list[str]:
    """按出现顺序取出正文里的公式（去重，忽略代码块 / 行内代码）。"""
    text = _strip_code(md)
    ordered: list[str] = []
    seen: set[str] = set()
    for m in _MATH_RE.finditer(text):
        tex = (m.group("display") or m.group("inline") or "").strip()
        if tex and tex not in seen:
            seen.add(tex)
            ordered.append(tex)
    return ordered


def render_math_png(
    tex: str, display: bool = False, size_px: int = 16
) -> bytes | None:
    """把公式渲染成透明底 PNG；matplotlib 不支持该公式时返回 None。"""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        # px -> pt（约 0.75）；块级公式放大 1.6 倍
        fontsize = max(size_px, 8) * (1.6 if display else 1.0) * 0.75
        fig = plt.figure(figsize=(0.01, 0.01), dpi=200)
        try:
            fig.text(0, 0, f"${normalize_tex(tex)}$", fontsize=fontsize)
            buf = io.BytesIO()
            fig.savefig(
                buf,
                format="png",
                bbox_inches="tight",
                pad_inches=0.05,
                transparent=True,
            )
        finally:
            plt.close(fig)
        return buf.getvalue()
    except Exception:  # noqa: BLE001  —— 任何渲染失败都降级为原文
        return None
