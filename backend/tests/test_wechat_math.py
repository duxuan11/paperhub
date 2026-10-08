"""公式提取 / 归一化 / 渲染测试（无需数据库 / Redis / 微信接口）。"""

import pytest

from app.core.config import settings  # noqa: F401  —— 注册仓库根目录到 sys.path

from publishers.wechat.math import extract_math, normalize_tex, render_math_png


def test_normalize_common_macros():
    assert normalize_tex(r"\delta \ge 0.25") == r"\delta \geq 0.25"
    assert normalize_tex(r"a \le b") == r"a \leq b"
    assert normalize_tex(r"a \geq b") == r"a \geq b"  # 已归一化的不被重复改
    assert normalize_tex(r"x \neq y") == r"x \neq y"


def test_extract_math_dedupes_and_ignores_code():
    md = "公式 $a$ 与 $a$，块级 $$b+c$$，价格 $100，代码 `$x$`。"
    assert extract_math(md) == ["a", "b+c"]


def test_extract_math_ignores_fenced_code():
    md = "```\n$x$\n```\n\n正文 $y$"
    assert extract_math(md) == ["y"]


def test_extract_math_multiline_display():
    md = "$$\nx = y\n+ z\n$$"
    assert extract_math(md) == ["x = y\n+ z"]


def test_extract_math_empty():
    assert extract_math("没有任何公式") == []


@pytest.mark.parametrize(
    "tex",
    [
        r"X = [\alpha, h_m, l_h, g_{ext}]",
        r"\delta \ge 0.25",
        r"l_h \ge 100\ \mu m",
        r"\alpha \in [26°, 90°]",
        r"V_i",
        r"f_1",
        r"\tau_s",
    ],
)
def test_render_math_png_produces_png(tex):
    png = render_math_png(tex, size_px=16)
    assert png is not None
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_math_png_returns_none_on_unsupported():
    assert render_math_png(r"\begin{align} a &= b \end{align}") is None
