# 文章编辑器：图片管理与公式渲染 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让文章编辑器可以排序 / 增 / 删文章图片（修正 YOLO 检测顺序），并让 `$...$` 公式在右侧公众号预览和发布到微信时都正确渲染。

**Architecture:** 前端新增图片操作纯逻辑模块 + 左栏 Tab 面板，改动即时 PATCH；公式在预览端用 KaTeX 渲染（渲染器通过依赖注入 `renderMath`，保持可测），发布端由后端把公式用 matplotlib 渲染成 PNG、走现有 `media/uploadimg` 换成 mmbiz URL 插入正文。

**Tech Stack:** Next.js 15 / React 19 / TypeScript、katex、node:test（类型擦除）、FastAPI / SQLAlchemy、pytest、matplotlib（mathtext）。

## Global Constraints

- 图片占位符语法不变：正文仍用 `{{figure:N}}`，按下标引用 `Article.images[N]`；不改 `Article.images` 数据类型（`list[str] | None`）。
- 排序语义 = 换图不换位（只重排数组，不改正文）；删除 = 下标前移（`> index` 的引用 -1，`=== index` 的引用删除）。
- 公式语法（前后端必须一致）：行内 `$...$`（起始 `$` 后非空白、结束 `$` 前非空白、内容不含换行 / 反引号 / `$`）；块级 `$$...$$`（独占一行或跨行围栏）；`$100` 这类不当作公式。
- 公众号正文只能有 inline style，不能出现 `<style>` / `class` / 外部 CSS。
- 公式渲染失败必须降级为 `$...$` 原文，不得中断发布。
- 后端不写数据库迁移（`create_all` 自动建表；本次无新表）。
- 不要初始化 ESLint（`npx eslint --init` 之类一律不做）。
- 测试命令：前端 `cd frontend && npx tsc --noEmit`、`cd frontend && npm test`；后端 `cd backend && uv run pytest -q`。
- 预览（KaTeX）与发布（matplotlib）像素级不一致是已接受的取舍，不要试图统一。

---

### Task 1: 前端图片操作纯逻辑

**Files:**
- Create: `frontend/lib/articleImages.ts`
- Test: `frontend/tests/articleImages.test.mjs`
- Modify: `frontend/package.json`（`test` 脚本加入新测试）

**Interfaces:**
- Consumes: 无。
- Produces:
  - `moveImage(images: string[], from: number, to: number): string[]`
  - `removeImage(content: string, images: string[], index: number): { content: string; images: string[] }`
  - `appendImage(images: string[], key: string): { images: string[]; index: number }`
  - `insertImageAtCursor(content: string, selectionStart: number, selectionEnd: number, index: number, alt: string): { content: string; cursor: number }`

- [ ] **Step 1: 写失败测试**

Create `frontend/tests/articleImages.test.mjs`:

```js
/**
 * 文章图片操作纯逻辑测试（node:test + 类型擦除）。
 *
 * 运行：npm --prefix frontend test
 */

import test from "node:test";
import assert from "node:assert/strict";

import {
  appendImage,
  insertImageAtCursor,
  moveImage,
  removeImage,
} from "../lib/articleImages.ts";

test("moveImage 换图不换位并返回新数组", () => {
  const images = ["a", "b", "c"];
  assert.deepEqual(moveImage(images, 0, 2), ["b", "c", "a"]);
  assert.deepEqual(moveImage(images, 2, 0), ["c", "a", "b"]);
  assert.deepEqual(images, ["a", "b", "c"]); // 入参不被修改
  assert.deepEqual(moveImage(images, 1, 1), ["a", "b", "c"]);
});

test("removeImage 删除独占一行的图片引用并重编号", () => {
  const content = [
    "# T",
    "",
    "![Figure 1]({{figure:0}})",
    "",
    "![Figure 2]({{figure:1}})",
    "",
    "![Figure 3]({{figure:2}})",
  ].join("\n");
  const { content: out, images } = removeImage(content, ["a", "b", "c"], 1);
  assert.deepEqual(images, ["a", "c"]);
  assert.ok(out.includes("![Figure 1]({{figure:0}})"));
  assert.ok(!out.includes("Figure 2")); // 被删项整行移除
  assert.ok(out.includes("![Figure 3]({{figure:1}})")); // 原 figure:2 前移
});

test("removeImage 删除内联占位符并重编号", () => {
  const { content: out, images } = removeImage(
    "看图 $x$ 和 {{figure:2}} 以及 {{figure:0}}",
    ["a", "b", "c"],
    1
  );
  assert.deepEqual(images, ["a", "c"]);
  assert.equal(out, "看图 $x$ 和 {{figure:1}} 以及 {{figure:0}}");
});

test("removeImage 下标越界时原样返回", () => {
  const { content, images } = removeImage("x {{figure:0}}", ["a"], 5);
  assert.equal(content, "x {{figure:0}}");
  assert.deepEqual(images, ["a"]);
});

test("appendImage 追加并返回新下标", () => {
  assert.deepEqual(appendImage(["a"], "b"), { images: ["a", "b"], index: 1 });
});

test("insertImageAtCursor 在行中插入独立图片行", () => {
  const r = insertImageAtCursor("abc", 1, 1, 0, "Figure 1");
  assert.equal(r.content, "a\n![Figure 1]({{figure:0}})\nbc");
  assert.equal(r.cursor, "a\n![Figure 1]({{figure:0}})\n".length);
});

test("insertImageAtCursor 替换选区", () => {
  const r = insertImageAtCursor("abcdef", 1, 4, 2, "Figure 3");
  assert.equal(r.content, "a\n![Figure 3]({{figure:2}})\nef");
});

test("insertImageAtCursor 空正文开头", () => {
  const r = insertImageAtCursor("", 0, 0, 0, "F");
  assert.equal(r.content, "![F]({{figure:0}})\n");
  assert.equal(r.cursor, r.content.length);
});
```

Modify `frontend/package.json` 的 `test` 脚本，加入 `tests/articleImages.test.mjs`：

```json
"test": "node --experimental-strip-types --test tests/themeConfig.test.mjs tests/aiAnalysis.test.mjs tests/figures.test.mjs tests/articleImages.test.mjs"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npm test`
Expected: FAIL，报错指向 `Cannot find module '../lib/articleImages.ts'`。

- [ ] **Step 3: 写最小实现**

Create `frontend/lib/articleImages.ts`:

```ts
/**
 * 文章图片操作纯逻辑（node:test 可测，不依赖 React / DOM）。
 *
 * 占位符约定：正文 `![...]({{figure:N}})` 按下标引用 `Article.images[N]`。
 * - 排序 = 换图不换位：只重排数组，不改正文（修正 YOLO 顺序）。
 * - 删除 = 下标前移：删掉 `images[index]`，并把正文里 `> index` 的下标 -1，
 *   `=== index` 的引用删除，避免悬空。
 */

const IMAGE_LINE_RE = /^!\[([^\]]*)\]\(\{\{figure:(\d+)\}\}\)$/;
const FIGURE_TOKEN_RE = /\{\{figure:(\d+)\}\}/g;

/** 换图不换位：把 from 位置的图移到 to，返回新数组（不改入参）。 */
export function moveImage(images: string[], from: number, to: number): string[] {
  if (from === to || from < 0 || from >= images.length) return [...images];
  const next = [...images];
  const [item] = next.splice(from, 1);
  next.splice(Math.max(0, Math.min(to, next.length)), 0, item);
  return next;
}

/** 删除 images[index]，并把正文里受影响的 {{figure:N}} 重编号 / 删除。 */
export function removeImage(
  content: string,
  images: string[],
  index: number
): { content: string; images: string[] } {
  if (index < 0 || index >= images.length) {
    return { content, images: [...images] };
  }
  const nextImages = images.filter((_, i) => i !== index);
  const kept = content.split("\n").filter((line) => {
    const m = IMAGE_LINE_RE.exec(line.trim());
    return !(m && Number(m[2]) === index);
  });
  let nextContent = kept.join("\n").replace(FIGURE_TOKEN_RE, (token, n: string) => {
    const i = Number(n);
    if (i === index) return "";
    if (i > index) return `{{figure:${i - 1}}}`;
    return token;
  });
  nextContent = nextContent.replace(/\n{3,}/g, "\n\n");
  return { content: nextContent, images: nextImages };
}

/** 追加一张图，返回新数组与它的下标。 */
export function appendImage(
  images: string[],
  key: string
): { images: string[]; index: number } {
  const next = [...images, key];
  return { images: next, index: next.length - 1 };
}

/** 在光标 / 选区处插入独立一行的图片引用，返回新正文与新光标位。 */
export function insertImageAtCursor(
  content: string,
  selectionStart: number,
  selectionEnd: number,
  index: number,
  alt: string
): { content: string; cursor: number } {
  const start = Math.max(0, Math.min(selectionStart, content.length));
  const end = Math.max(start, Math.min(selectionEnd, content.length));
  const before = content.slice(0, start);
  const after = content.slice(end);
  const image = `![${alt}]({{figure:${index}}})`;
  const lead = before === "" || before.endsWith("\n") ? "" : "\n";
  const inserted = `${lead}${image}\n`;
  return {
    content: `${before}${inserted}${after}`,
    cursor: (before + inserted).length,
  };
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd frontend && npm test && npx tsc --noEmit`
Expected: 全部 PASS，tsc 无输出。

- [ ] **Step 5: 提交**

```bash
git add frontend/lib/articleImages.ts frontend/tests/articleImages.test.mjs frontend/package.json
git commit -m "feat(frontend): 文章图片操作纯逻辑（排序/删除重编号/光标插入）"
```

---

### Task 2: 后端图片上传接口 + PATCH images

**Files:**
- Modify: `backend/app/schemas.py`（`ArticleUpdateRequest`）
- Modify: `backend/app/api/v1/articles.py`（`_cover_ext` → `_image_ext`，新增接口）
- Test: `backend/tests/test_article_images.py`

**Interfaces:**
- Consumes: 无。
- Produces:
  - `ArticleUpdateRequest.images: list[str] | None`
  - `POST /api/v1/articles/{article_id}/images`（multipart `file`）→ `ArticleOut`
  - `backend/app/api/v1/articles.py::_image_ext(content_type, filename) -> str | None`
  - `backend/app/api/v1/articles.py::_append_image(images, key) -> list[str]`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_article_images.py`:

```python
"""文章图片管理相关纯逻辑测试（无需数据库 / Redis / 微信接口）。"""

from app.core.config import settings  # noqa: F401  —— 注册仓库根目录到 sys.path

from app.api.v1.articles import _append_image, _image_ext
from app.schemas import ArticleUpdateRequest


def test_image_ext_accepts_supported_types():
    assert _image_ext("image/png", "x") == ".png"
    assert _image_ext("image/jpeg", "x") == ".jpg"
    assert _image_ext(None, "a.webp") == ".webp"
    assert _image_ext(None, "a.gif") == ".gif"
    assert _image_ext("application/pdf", "a.pdf") is None
    assert _image_ext("image/svg+xml", "a.svg") is None


def test_append_image_handles_none():
    assert _append_image(None, "k") == ["k"]
    assert _append_image(["a"], "b") == ["a", "b"]


def test_article_update_request_accepts_images():
    req = ArticleUpdateRequest(images=["a", "b"])
    assert req.model_dump(exclude_unset=True) == {"images": ["a", "b"]}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && uv run pytest tests/test_article_images.py -q`
Expected: FAIL，`ImportError: cannot import name '_append_image'`。

- [ ] **Step 3: 写最小实现**

Modify `backend/app/schemas.py` 的 `ArticleUpdateRequest`（第 287 行附近），追加一行：

```python
class ArticleUpdateRequest(BaseModel):
    title: str | None = None
    summary: str | None = None
    content: str | None = None
    html: str | None = None
    author: str | None = None
    theme: str | None = None
    cover_image: str | None = None
    images: list[str] | None = None
```

Modify `backend/app/api/v1/articles.py`：

把 `_cover_ext` 改名为 `_image_ext`（并把唯一的调用点一起改）：

```python
def _image_ext(content_type: str | None, filename: str | None) -> str | None:
    ext = _COVER_EXT.get((content_type or "").lower())
    if ext:
        return ext
    suffix = Path(filename or "").suffix.lower()
    return suffix if suffix in {v for v in _COVER_EXT.values()} else None


def _append_image(images: list[str] | None, key: str) -> list[str]:
    """把新图 key 追加到文章图片列表（None 视作空列表）。"""
    return [*(images or []), key]
```

`upload_article_cover` 里的 `_cover_ext(...)` 改为 `_image_ext(...)`。然后在 `upload_article_cover` 之后新增：

```python
@router.post("/{article_id}/images", response_model=ArticleOut)
async def upload_article_image(
    article_id: str,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    """上传一张正文配图，追加到 article.images（返回下标即最后一项）。

    编辑器新增图片后据此在光标处插入 `![alt]({{figure:N}})`。
    """
    art = await repositories.get_article(session, article_id)
    if not art:
        raise HTTPException(status_code=404, detail="文章不存在")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="图片文件为空")
    if len(data) > _MAX_COVER_BYTES:
        raise HTTPException(status_code=400, detail="图片不能超过 10MB")
    ext = _image_ext(file.content_type, file.filename)
    if not ext:
        raise HTTPException(
            status_code=400, detail="仅支持 PNG / JPG / WEBP / GIF 图片"
        )
    key = f"articles/{article_id}/images/{uuid.uuid4().hex[:12]}{ext}"
    storage.put_bytes(key, data, file.content_type or "image/png")
    art.images = _append_image(art.images, key)
    await session.commit()
    await session.refresh(art)
    return art
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && uv run pytest tests/test_article_images.py -q && uv run pytest -q`
Expected: 新测试 PASS，整个后端测试套件不回归。

- [ ] **Step 5: 提交**

```bash
git add backend/app/schemas.py backend/app/api/v1/articles.py backend/tests/test_article_images.py
git commit -m "feat(backend): 文章配图上传接口 + PATCH images"
```

---

### Task 3: 后端公式模块（归一化 / 提取 / 渲染）

**Files:**
- Modify: `backend/pyproject.toml`（新增 `matplotlib`）
- Create: `publishers/wechat/math.py`
- Test: `backend/tests/test_wechat_math.py`

**Interfaces:**
- Consumes: 无。
- Produces:
  - `publishers/wechat/math.py::INLINE_MATH_RE`（已编译的正则，含命名组 `inline`）
  - `normalize_tex(tex: str) -> str`
  - `extract_math(md: str) -> list[str]`
  - `render_math_png(tex: str, display: bool = False, size_px: int = 16) -> bytes | None`

- [ ] **Step 1: 安装依赖**

Run: `cd backend && uv add "matplotlib>=3.9"`
Expected: `pyproject.toml` / `uv.lock` 更新，输出 "Resolved ... / Installed ... matplotlib"。

- [ ] **Step 2: 写失败测试**

Create `backend/tests/test_wechat_math.py`:

```python
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
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd backend && uv run pytest tests/test_wechat_math.py -q`
Expected: FAIL，`ModuleNotFoundError: No module named 'publishers.wechat.math'`。

- [ ] **Step 4: 写最小实现**

Create `publishers/wechat/math.py`:

```python
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
        # 用函数替换，避免 dst 里的 ``\g`` 被 re.sub 当成组引用
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
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && uv run pytest tests/test_wechat_math.py -q`
Expected: 全部 PASS（含 7 个参数化渲染用例）。

- [ ] **Step 6: 提交**

```bash
git add backend/pyproject.toml backend/uv.lock publishers/wechat/math.py backend/tests/test_wechat_math.py
git commit -m "feat(backend): 公式归一化/提取/matplotlib 渲染模块"
```

---

### Task 4: 渲染器支持 math_map

**Files:**
- Modify: `publishers/wechat/renderer.py`
- Test: `backend/tests/test_wechat_math.py`（追加渲染器用例）

**Interfaces:**
- Consumes: `publishers.wechat.math.INLINE_MATH_RE`、`normalize_tex`（Task 3）。
- Produces: `render_markdown_html(md, theme=None, image_map=None, math_map=None) -> str`；`math_map: dict[str, str]` 的 key 是**归一化后的 tex**，value 是可访问 URL。

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_wechat_math.py` 末尾追加：

```python
from publishers.wechat.renderer import render_markdown_html


def test_renderer_replaces_inline_math_with_img_when_mapped():
    html = render_markdown_html(
        "目标 $V_i$ 最大", math_map={r"V_i": "https://mmbiz/x.png"}
    )
    assert '<img src="https://mmbiz/x.png"' in html
    assert "$V_i$" not in html


def test_renderer_falls_back_to_literal_when_unmapped():
    html = render_markdown_html("目标 $V_i$ 最大")
    assert "$V_i$" in html


def test_renderer_renders_display_math_centered():
    html = render_markdown_html("$$a+b$$", math_map={"a+b": "https://mmbiz/d.png"})
    assert 'src="https://mmbiz/d.png"' in html
    assert "text-align:center" in html


def test_renderer_ignores_dollar_in_inline_code():
    html = render_markdown_html("价格 `$x$`", math_map={"x": "https://mmbiz/x.png"})
    assert "https://mmbiz/x.png" not in html
    assert "$x$" in html


def test_renderer_renders_math_in_list_items():
    md = "- 目标：$V_i$\n- 约束：$\\delta \\ge 0.25$"
    html = render_markdown_html(
        md,
        math_map={r"V_i": "https://mmbiz/v.png", r"\delta \geq 0.25": "https://mmbiz/d.png"},
    )
    assert "https://mmbiz/v.png" in html
    assert "https://mmbiz/d.png" in html
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && uv run pytest tests/test_wechat_math.py -q`
Expected: FAIL，`TypeError: render_markdown_html() got an unexpected keyword argument 'math_map'`。

- [ ] **Step 3: 写最小实现**

Modify `publishers/wechat/renderer.py`：

在 import 区加：

```python
from publishers.wechat.math import INLINE_MATH_RE, normalize_tex
```

在 `_tag` 之后新增（`escape` 与 `_attr` 已在文件内定义）：

```python
_CODE_HTML_RE = re.compile(r"<code[^>]*>.*?</code>", re.S)


def _math_html(
    tex: str, math_map: dict[str, str] | None, display: bool = False
) -> str:
    """公式 → 图片；math_map 未命中时退回 $...$ 原文。"""
    url = (math_map or {}).get(normalize_tex(tex))
    if url:
        css = (
            "display:block;margin:0 auto;max-width:100%"
            if display
            else "vertical-align:middle;max-width:100%"
        )
        return f'<img src="{_attr(url)}" alt="{_attr(tex)}" style="{css}">'
    return escape(f"$${tex}$$" if display else f"${tex}$")


def _math_only(text: str, math_map: dict[str, str] | None) -> str:
    return INLINE_MATH_RE.sub(
        lambda m: _math_html(html.unescape(m.group("inline")), math_map), text
    )


def _replace_inline_math(text: str, math_map: dict[str, str] | None) -> str:
    """在已转义的文本里替换行内公式，跳过 <code> 区域。"""
    if not math_map:
        return text
    out: list[str] = []
    pos = 0
    for m in _CODE_HTML_RE.finditer(text):
        out.append(_math_only(text[pos : m.start()], math_map))
        out.append(m.group(0))
        pos = m.end()
    out.append(_math_only(text[pos:], math_map))
    return "".join(out)
```

把 `_inline` 的签名与结尾改成：

```python
def _inline(
    text: str,
    theme: WeChatTheme,
    image_map: dict[str, str],
    math_map: dict[str, str] | None = None,
) -> str:
    """行内元素：先转义，再依次处理图片/链接/加粗/斜体/行内代码/公式。"""
    text = escape(text)
    # ...（中间 images / links / strong / em / code 五段正则保持不变）...
    text = re.sub(
        r"`(.+?)`",
        lambda m: _tag("code", m.group(1), theme.css("code")),
        text,
    )
    return _replace_inline_math(text, math_map)
```

`_render_table` 签名加 `math_map`，并把其中两处 `_inline(c, theme, image_map)` 改成 `_inline(c, theme, image_map, math_map)`：

```python
def _render_table(
    lines: list[str],
    start: int,
    theme: WeChatTheme,
    image_map: dict[str, str],
    math_map: dict[str, str] | None = None,
) -> tuple[str, int]:
```

新增块级公式取词 helper（放在 `_render_table` 之前）：

```python
def _take_display_math(lines: list[str], start: int) -> tuple[str, int]:
    """从 lines[start] 取出一段块级公式，返回 (tex, 下一行索引)。"""
    first = lines[start].strip()
    if first.endswith("$$") and len(first) > 4:
        return first[2:-2].strip(), start + 1
    body: list[str] = [first[2:]]
    i = start + 1
    while i < len(lines):
        line = lines[i].strip()
        if line.endswith("$$"):
            body.append(line[:-2])
            return "\n".join(body).strip(), i + 1
        body.append(lines[i])
        i += 1
    return "\n".join(body).strip(), i
```

`render_markdown_html` 签名与内部：

```python
def render_markdown_html(
    md: str,
    theme: WeChatTheme | None = None,
    image_map: dict[str, str] | None = None,
    math_map: dict[str, str] | None = None,
) -> str:
    theme = theme or get_theme(DEFAULT_THEME_ID)
    image_map = image_map or {}
    # ...（lines / blocks / i / total 初始化不变）...
```

所有 `_inline(..., theme, image_map)` 调用补上 `math_map`（标题、callout Title/Text、blockquote、list item、caption、paragraph），`_render_table(...)` 调用补 `math_map`。在「普通段落」分支之前插入块级公式分支：

```python
        # 块级公式（独占一行或 $$ 围栏）
        if stripped.startswith("$$"):
            tex, i = _take_display_math(lines, i)
            blocks.append(
                _tag(
                    "p",
                    _math_html(tex, math_map, display=True),
                    {"margin": "0", "text-align": "center"},
                )
            )
            continue
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && uv run pytest tests/test_wechat_math.py -q && uv run pytest -q`
Expected: 新用例 PASS，`test_wechat_theme.py` / `test_wechat_publish.py` 无回归（`markdown_to_wechat_html` 不传 `math_map`，行为不变）。

- [ ] **Step 5: 提交**

```bash
git add publishers/wechat/renderer.py backend/tests/test_wechat_math.py
git commit -m "feat(backend): 公众号渲染器支持公式图片（math_map）"
```

---

### Task 5: 发布链路接线（publisher + worker）

**Files:**
- Modify: `publishers/wechat/publisher.py`（`build_article_payload` 透传 `math_map`）
- Modify: `backend/app/workers/tasks.py`（`_upload_math_images` + 发布任务接线）
- Test: `backend/tests/test_wechat_publish.py`（追加用例）

**Interfaces:**
- Consumes: Task 3 的 `extract_math / normalize_tex / render_math_png`；Task 4 的 `render_markdown_html(..., math_map=...)`。
- Produces:
  - `build_article_payload(..., math_map: dict[str, str] | None = None)`
  - `backend/app/workers/tasks.py::_upload_math_images(publisher, content: str, size_px: int = 16) -> dict[str, str]`
  - `backend/app/workers/tasks.py::_theme_font_px(theme_obj, default: int = 16) -> int`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_wechat_publish.py` 末尾追加：

```python
def test_build_article_payload_renders_math_images():
    payload = build_article_payload(
        "T",
        "目标 $V_i$ 最大化",
        {},
        math_map={r"V_i": "https://mmbiz/m.png"},
    )
    assert '<img src="https://mmbiz/m.png"' in payload["content"]


def test_upload_math_images_maps_formulas(monkeypatch):
    from app.workers import tasks

    async def no_redis():
        raise RuntimeError("no redis in test")

    monkeypatch.setattr(tasks, "get_arq_pool", no_redis)
    publisher = MockWeChatPublisher()
    mapping = run(tasks._upload_math_images(publisher, "目标 $V_i$ 最大，约束 $\\delta \\ge 0.25$"))
    assert r"V_i" in mapping
    assert r"\delta \geq 0.25" in mapping  # key 是归一化后的 tex
    assert mapping[r"V_i"].startswith("mock-image-")


def test_upload_math_images_empty_content():
    from app.workers import tasks

    publisher = MockWeChatPublisher()
    assert run(tasks._upload_math_images(publisher, "没有公式")) == {}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && uv run pytest tests/test_wechat_publish.py -q`
Expected: FAIL，`TypeError: build_article_payload() got an unexpected keyword argument 'math_map'` 与 `AttributeError: module ... has no attribute '_upload_math_images'`。

- [ ] **Step 3: 写最小实现**

Modify `publishers/wechat/publisher.py` 的 `build_article_payload`：

```python
def build_article_payload(
    title: str,
    content_md: str,
    image_map: dict[str, str] | None = None,
    *,
    thumb_media_id: str = "",
    author: str = "PaperHub",
    digest: str = "",
    content_source_url: str = "",
    theme: str | WeChatTheme | None = None,
    math_map: dict[str, str] | None = None,
) -> dict:
    # ...（theme_obj 解析不变）...
    html = render_markdown_html(content_md, theme_obj, image_map, math_map)
    # ...（MAX_CONTENT_LEN 检查与 return 不变）...
```

Modify `backend/app/workers/tasks.py`：

顶部 import 区加 `import re`（放在 `import hashlib` 之前/之后均可）。

在 `_upload_content_images` 之后新增：

```python
def _theme_font_px(theme_obj, default: int = 16) -> int:
    """从主题的正文样式里取字号（px），解析失败用 default。"""
    raw = (theme_obj.css("paragraph") or {}).get("font-size", "")
    m = re.match(r"(\d+(?:\.\d+)?)px", str(raw))
    return int(float(m.group(1))) if m else default


async def _upload_math_images(
    publisher, content: str, size_px: int = 16
) -> dict[str, str]:
    """把正文中的公式渲染成图片并上传微信，返回 {归一化 tex: URL}。

    按 sha1(tex) 在 Redis 缓存 URL，避免同一公式反复渲染上传；
    渲染 / 上传失败只跳过该条（渲染器会退回原文），不阻断发布。
    """
    from publishers.wechat.math import extract_math, normalize_tex, render_math_png

    mapping: dict[str, str] = {}
    formulas = extract_math(content)
    if not formulas:
        return mapping

    pool = None
    try:
        pool = await get_arq_pool()
    except Exception as e:  # noqa: BLE001
        log.warning("公式图片缓存不可用，跳过缓存: %s", e)

    for tex in formulas:
        key = normalize_tex(tex)
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
        cache_key = f"wechat:math:{digest}"
        if pool is not None:
            try:
                cached = await pool.get(cache_key)
                if cached:
                    mapping[key] = (
                        cached.decode() if isinstance(cached, bytes) else str(cached)
                    )
                    continue
            except Exception as e:  # noqa: BLE001
                log.warning("公式图片缓存读取失败: %s", e)

        png = render_math_png(tex, size_px=size_px)
        if not png:
            log.warning("公式渲染失败，正文将保留原文: %s", tex)
            continue
        try:
            url = await publisher.upload_content_image(
                png, f"math-{digest[:8]}.png"
            )
        except Exception as e:  # noqa: BLE001
            log.warning("公式图片上传微信失败，正文将保留原文: %s (%s)", tex, e)
            continue
        mapping[key] = url
        if pool is not None:
            try:
                await pool.set(cache_key, url)
            except Exception as e:  # noqa: BLE001
                log.warning("公式图片缓存写入失败: %s", e)

    return mapping
```

在 `publish_wechat_article` 里，把：

```python
        image_map = await _upload_content_images(publisher, images)
        thumb_media_id = await _ensure_thumb_media_id(publisher, images, cover_image)
        payload = build_article_payload(
            title,
            content,
            image_map,
            thumb_media_id=thumb_media_id,
            author=author,
            digest=digest,
            theme=theme_obj,
        )
```

改为：

```python
        image_map = await _upload_content_images(publisher, images)
        math_map = await _upload_math_images(
            publisher, content, size_px=_theme_font_px(theme_obj)
        )
        thumb_media_id = await _ensure_thumb_media_id(publisher, images, cover_image)
        payload = build_article_payload(
            title,
            content,
            image_map,
            thumb_media_id=thumb_media_id,
            author=author,
            digest=digest,
            theme=theme_obj,
            math_map=math_map,
        )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && uv run pytest tests/test_wechat_publish.py -q && uv run pytest -q`
Expected: 新用例 PASS，全量后端测试 PASS。

- [ ] **Step 5: 提交**

```bash
git add publishers/wechat/publisher.py backend/app/workers/tasks.py backend/tests/test_wechat_publish.py
git commit -m "feat(backend): 发布链路把公式转图片上传微信"
```

---

### Task 6: 前端预览公式渲染（KaTeX）

**Files:**
- Modify: `frontend/lib/wechatTheme.ts`
- Modify: `frontend/components/WeChatPreview.tsx`
- Test: `frontend/tests/wechatMath.test.mjs`
- Modify: `frontend/package.json`（`test` 脚本加入新测试）

**Interfaces:**
- Consumes: Task 4 定义的公式语法（必须一致）。
- Produces: `RenderOptions.renderMath?: (tex: string, display: boolean) => string`。

- [ ] **Step 1: 写失败测试**

Create `frontend/tests/wechatMath.test.mjs`:

```js
/**
 * 公众号渲染器公式切段测试（node:test + 类型擦除）。
 *
 * 运行：npm --prefix frontend test
 */

import test from "node:test";
import assert from "node:assert/strict";

import { renderWechatHtml } from "../lib/wechatTheme.ts";

const theme = { id: "t", name: "T", styles: {} };
const renderMath = (tex, display) =>
  `<span data-math="${display ? "block" : "inline"}">${tex}</span>`;

test("段落内行内公式交给 renderMath", () => {
  const html = renderWechatHtml("目标 $V_i$ 最大", theme, { renderMath });
  assert.ok(html.includes('data-math="inline">V_i<'));
});

test("列表项与表格单元格内的公式也被渲染", () => {
  const md = "- **a**：$\\alpha$\n\n| A | B |\n| - | - |\n| $x$ | y |";
  const html = renderWechatHtml(md, theme, { renderMath });
  assert.ok(html.includes('data-math="inline">\\alpha<'));
  assert.ok(html.includes('data-math="inline">x<'));
});

test("块级公式单独渲染", () => {
  const html = renderWechatHtml("$$a+b$$", theme, { renderMath });
  assert.ok(html.includes('data-math="block">a+b<'));
});

test("$100 与代码内 $ 不当作公式", () => {
  const html = renderWechatHtml("价格 $100，代码 `$x$`", theme, { renderMath });
  assert.ok(!html.includes("data-math"));
});

test("不传 renderMath 时行为与旧版一致", () => {
  const html = renderWechatHtml("目标 $V_i$ 最大", theme);
  assert.ok(html.includes("$V_i$"));
  assert.ok(!html.includes("data-math"));
});
```

Modify `frontend/package.json` 的 `test` 脚本，追加 `tests/wechatMath.test.mjs`：

```json
"test": "node --experimental-strip-types --test tests/themeConfig.test.mjs tests/aiAnalysis.test.mjs tests/figures.test.mjs tests/articleImages.test.mjs tests/wechatMath.test.mjs"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npm test`
Expected: `wechatMath` 用例 FAIL（`data-math` 不出现、块级公式未渲染）。

- [ ] **Step 3: 写最小实现**

Modify `frontend/lib/wechatTheme.ts`：

`RenderOptions` 追加字段：

```ts
export interface RenderOptions {
  /** {占位名: URL}，替换 ![]({{figure:N}}) 里的占位符 */
  imageMap?: Record<string, string>;
  /** 把相对图片路径（如 images/x.png）解析为可访问 URL */
  resolveSrc?: (src: string) => string;
  /** 公式渲染器（预览注入 KaTeX）；不传则公式保持原文 */
  renderMath?: (tex: string, display: boolean) => string;
}
```

在正则常量区追加：

```ts
// 行内公式：起始 $ 后非空白、结束 $ 前非空白、内容不含换行 / 反引号 / $
const INLINE_MATH_RE = /(?<![\\$])\$(?![\s$])([^$\n`]+?)(?<![\s\\])(?<![\\$])\$/g;
// 已转义文本里的行内代码区域，公式要跳过
const CODE_HTML_RE = /<code[^>]*>[\s\S]*?<\/code>/g;
```

在 `escapeAttr` 之后追加：

```ts
function unescapeHtml(text: string): string {
  return text.replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">");
}

function replaceInlineMath(
  text: string,
  render: (tex: string, display: boolean) => string
): string {
  return text.replace(INLINE_MATH_RE, (_m, tex: string) =>
    render(unescapeHtml(tex), false)
  );
}

/** 在已转义的文本里替换行内公式，跳过 <code> 区域。 */
function applyMath(text: string, opts: RenderOptions): string {
  const render = opts.renderMath;
  if (!render) return text;
  const parts: string[] = [];
  let pos = 0;
  for (const m of text.matchAll(CODE_HTML_RE)) {
    const start = m.index ?? 0;
    parts.push(replaceInlineMath(text.slice(pos, start), render));
    parts.push(m[0]);
    pos = start + m[0].length;
  }
  parts.push(replaceInlineMath(text.slice(pos), render));
  return parts.join("");
}
```

`inline()` 结尾追加一行（在 `` `code` `` 替换之后）：

```ts
  out = out.replace(
    /`(.+?)`/g,
    (_m, s: string) => tag("code", s, themeCss(theme, "code"))
  );
  return applyMath(out, opts);
```

`tag` 之后或 `renderTable` 附近追加块级公式 helper：

```ts
/** 从 lines[start] 取出一段块级公式，返回 (tex, 下一行索引)。 */
function takeDisplayMath(
  lines: string[],
  start: number
): { tex: string; next: number } {
  const first = lines[start].trim();
  if (first.endsWith("$$") && first.length > 4) {
    return { tex: first.slice(2, -2).trim(), next: start + 1 };
  }
  const body: string[] = [first.slice(2)];
  let i = start + 1;
  while (i < lines.length) {
    const line = lines[i].trim();
    if (line.endsWith("$$")) {
      body.push(line.slice(0, -2));
      return { tex: body.join("\n").trim(), next: i + 1 };
    }
    body.push(lines[i]);
    i += 1;
  }
  return { tex: body.join("\n").trim(), next: i };
}

function displayMathBlock(tex: string, theme: WechatTheme, opts: RenderOptions): string {
  const inner = opts.renderMath
    ? opts.renderMath(tex, true)
    : escapeHtml(`$$${tex}$$`);
  return tag("p", inner, { margin: "0", "text-align": "center" });
}
```

`renderWechatHtml` 主循环里，在「普通段落」之前插入：

```ts
    // 块级公式（独占一行或 $$ 围栏）
    if (stripped.startsWith("$$")) {
      const { tex, next } = takeDisplayMath(lines, i);
      blocks.push(displayMathBlock(tex, theme, opts));
      i = next;
      continue;
    }
```

Modify `frontend/components/WeChatPreview.tsx`：顶部 import 追加

```tsx
import katex from "katex";
import "katex/dist/katex.min.css";
```

`renderWechatHtml` 的 options 里加 `renderMath`：

```tsx
    return renderWechatHtml(content, theme, {
      resolveSrc: (src) => {
        if (!src) return src;
        if (/^(https?:)?\/\//.test(src) || src.startsWith("/") || src.startsWith("data:")) {
          return src;
        }
        return paperId ? fileUrl(`${paperId}/${src}`) : src;
      },
      renderMath: (tex, display) =>
        katex.renderToString(tex, {
          displayMode: display,
          throwOnError: false,
          strict: false,
        }),
    });
```

`useMemo` 依赖数组保持 `[content, theme, paperId]`。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd frontend && npm test && npx tsc --noEmit`
Expected: 全部 PASS，tsc 无输出。

- [ ] **Step 5: 提交**

```bash
git add frontend/lib/wechatTheme.ts frontend/components/WeChatPreview.tsx frontend/tests/wechatMath.test.mjs frontend/package.json
git commit -m "feat(frontend): 公众号预览用 KaTeX 渲染公式"
```

---

### Task 7: 跨语言公式语法 parity 测试

**Files:**
- Create: `tests/fixtures/math_syntax_cases.json`
- Create: `backend/tests/test_math_syntax_parity.py`
- Create: `frontend/tests/mathSyntaxParity.test.mjs`
- Modify: `frontend/package.json`（`test` 脚本加入新测试）

**Interfaces:**
- Consumes: `publishers/wechat/math.py::extract_math`（Task 3）；`frontend/lib/wechatTheme.ts::renderWechatHtml` 与 `RenderOptions.renderMath`（Task 6）。
- Produces: 共享夹具 `tests/fixtures/math_syntax_cases.json`，格式 `[{ "name": str, "markdown": str, "expected": [str] }]`（`expected` 为按首次出现顺序去重后的公式，跨行块级公式的换行保留）。前端与后端测试读同一份文件，任一侧语法漂移都会让对侧测试失败。

- [ ] **Step 1: 建共享夹具**

Create `tests/fixtures/math_syntax_cases.json`:

```json
[
  { "name": "inline simple", "markdown": "目标 $V_i$ 最大", "expected": ["V_i"] },
  { "name": "inline greek and subscript", "markdown": "$X = [\\alpha, h_m, l_h, g_{ext}]$", "expected": ["X = [\\alpha, h_m, l_h, g_{ext}]"] },
  { "name": "inline ge", "markdown": "$\\delta \\ge 0.25$", "expected": ["\\delta \\ge 0.25"] },
  { "name": "inline degree", "markdown": "$\\alpha \\in [26°, 90°]$", "expected": ["\\alpha \\in [26°, 90°]"] },
  { "name": "display single line", "markdown": "$$a+b$$", "expected": ["a+b"] },
  { "name": "display multiline", "markdown": "$$\nx = y\n+ z\n$$", "expected": ["x = y\n+ z"] },
  { "name": "price is not math", "markdown": "价格 $100，不含税", "expected": [] },
  { "name": "inline code ignored", "markdown": "代码 `$x$` 不是公式", "expected": [] },
  { "name": "fenced code ignored", "markdown": "```\n$y$\n```\n\n正文 $z$", "expected": ["z"] },
  { "name": "dedupe", "markdown": "$a$ 与 $a$", "expected": ["a"] },
  { "name": "in list and table", "markdown": "- 目标：$V_i$\n\n| A | B |\n| - | - |\n| $f_1$ | y |", "expected": ["V_i", "f_1"] },
  { "name": "escaped dollar", "markdown": "\\$5 不是公式", "expected": [] }
]
```

- [ ] **Step 2: 写 Python parity 测试**

Create `backend/tests/test_math_syntax_parity.py`:

```python
"""前后端公式语法 parity：两侧读同一份夹具，任一侧漂移都会失败。"""

import json
from pathlib import Path

import pytest

from app.core.config import settings  # noqa: F401  —— 注册仓库根目录到 sys.path

from publishers.wechat.math import extract_math

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "tests"
    / "fixtures"
    / "math_syntax_cases.json"
)
CASES = json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_backend_math_syntax_matches_fixture(case):
    assert extract_math(case["markdown"]) == case["expected"]
```

- [ ] **Step 3: 写 JS parity 测试**

Create `frontend/tests/mathSyntaxParity.test.mjs`:

```js
/**
 * 前后端公式语法 parity：读同一份夹具，用 renderMath 捕获前端实际识别的公式，
 * 按首次出现顺序去重后与 expected 比对。
 *
 * 运行：npm --prefix frontend test
 */

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { renderWechatHtml } from "../lib/wechatTheme.ts";

const theme = { id: "t", name: "T", styles: {} };
const fixtureUrl = new URL("../../tests/fixtures/math_syntax_cases.json", import.meta.url);
const cases = JSON.parse(readFileSync(fixtureUrl, "utf-8"));

for (const c of cases) {
  test(`frontend math syntax: ${c.name}`, () => {
    const seen = [];
    renderWechatHtml(c.markdown, theme, {
      renderMath: (tex) => {
        if (!seen.includes(tex)) seen.push(tex);
        return `<span>${tex}</span>`;
      },
    });
    assert.deepEqual(seen, c.expected);
  });
}
```

Modify `frontend/package.json` 的 `test` 脚本，追加 `tests/mathSyntaxParity.test.mjs`：

```json
"test": "node --experimental-strip-types --test tests/themeConfig.test.mjs tests/aiAnalysis.test.mjs tests/figures.test.mjs tests/articleImages.test.mjs tests/wechatMath.test.mjs tests/mathSyntaxParity.test.mjs"
```

- [ ] **Step 4: 两侧都跑，确认通过**

Run: `cd backend && uv run pytest tests/test_math_syntax_parity.py -q`
Expected: 12 个参数化用例 PASS。

Run: `cd frontend && npm test && npx tsc --noEmit`
Expected: parity 用例 PASS，tsc 无输出。

如果任一侧失败，说明 Task 3 / Task 6 的语法实现不一致：以夹具为准修实现（不是修夹具），并说明哪一侧偏了。

- [ ] **Step 5: 提交**

```bash
git add tests/fixtures/math_syntax_cases.json backend/tests/test_math_syntax_parity.py frontend/tests/mathSyntaxParity.test.mjs frontend/package.json
git commit -m "test: 前后端公式语法 parity 共享夹具"
```

---

### Task 8: 编辑器左栏图片管理 UI

**Files:**
- Modify: `frontend/lib/api.ts`（`apiUploadArticleImage`）
- Create: `frontend/components/ArticleImagePanel.tsx`
- Modify: `frontend/app/articles/[id]/edit/page.tsx`

**Interfaces:**
- Consumes: Task 1 的 `moveImage / removeImage / appendImage / insertImageAtCursor`；Task 2 的 `POST /articles/{id}/images` 与 `PATCH {images, content}`；现有 `GET /papers/{paper_id}/figures`。
- Produces: `<ArticleImagePanel />` 组件（props 见下）。

- [ ] **Step 1: 加前端上传 helper**

Modify `frontend/lib/api.ts`，在 `apiUploadCover` 之后追加：

```ts
export async function apiUploadArticleImage(articleId: string, file: File): Promise<any> {
  const fd = new FormData();
  fd.append("file", file);
  const r = await fetch(`${PROXY}/articles/${articleId}/images`, {
    method: "POST",
    body: fd,
  });
  if (!r.ok) throw new Error(await errorMessage(r));
  return r.json();
}
```

- [ ] **Step 2: 新建图片面板组件**

Create `frontend/components/ArticleImagePanel.tsx`:

```tsx
"use client";

import { useCallback, useRef, useState } from "react";
import { apiGet, fileUrl } from "@/lib/api";
import type { Figure } from "@/lib/types";

/**
 * 文章图片管理面板（编辑器左栏「图片」Tab）。
 *
 * - 拖拽排序：换图不换位，交回父组件 PATCH images；
 * - 删除 / 插入 / 从论文图库添加 / 本地上传：都交回父组件处理（父组件持有正文与光标）。
 */
export function ArticleImagePanel({
  images,
  paperId,
  onReorder,
  onDelete,
  onInsert,
  onAdd,
  onUpload,
}: {
  images: string[];
  paperId: string | null;
  onReorder: (from: number, to: number) => void;
  onDelete: (index: number) => void;
  onInsert: (index: number, alt: string) => void;
  onAdd: (key: string, alt: string) => void;
  onUpload: (file: File) => void;
}) {
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [overIndex, setOverIndex] = useState<number | null>(null);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [figures, setFigures] = useState<Figure[]>([]);
  const [loading, setLoading] = useState(false);
  const fileRef = useRef<HTMLInputElement | null>(null);

  const altOf = (index: number) => `Figure ${index + 1}`;

  const openLibrary = useCallback(async () => {
    if (!paperId) return;
    setLibraryOpen(true);
    setLoading(true);
    try {
      const all = await apiGet<Figure[]>(`/papers/${paperId}/figures`);
      setFigures(all.filter((f) => !images.includes(f.image_path)));
    } catch {
      setFigures([]);
    } finally {
      setLoading(false);
    }
  }, [paperId, images]);

  function dropAt(to: number) {
    if (dragIndex !== null && dragIndex !== to) onReorder(dragIndex, to);
    setDragIndex(null);
    setOverIndex(null);
  }

  return (
    <div className="flex-1 min-h-0 flex flex-col">
      <div className="flex-1 min-h-0 overflow-y-auto">
        {images.length === 0 && (
          <p className="px-4 py-4 text-[12px] text-neutral-400 leading-relaxed">
            暂无图片，可从论文图库添加或上传。
          </p>
        )}
        <ul className="py-2">
          {images.map((key, i) => (
            <li
              key={`${key}-${i}`}
              draggable
              onDragStart={() => setDragIndex(i)}
              onDragOver={(e) => {
                e.preventDefault();
                setOverIndex(i);
              }}
              onDrop={() => dropAt(i)}
              onDragEnd={() => {
                setDragIndex(null);
                setOverIndex(null);
              }}
              className={`group mx-2 mb-1 flex items-center gap-2 rounded-lg border px-2 py-1.5 ${
                overIndex === i
                  ? "border-brand-300 bg-brand-50"
                  : "border-neutral-200 bg-white"
              }`}
            >
              <span className="cursor-grab text-neutral-300 select-none" title="拖动排序">
                ⠿
              </span>
              <span className="w-5 shrink-0 text-[11px] tabular-nums text-neutral-400">
                #{i + 1}
              </span>
              <img
                src={fileUrl(key)}
                alt={altOf(i)}
                className="h-9 w-12 shrink-0 rounded border border-neutral-200 object-cover"
              />
              <span className="flex-1" />
              <button
                onClick={() => onInsert(i, altOf(i))}
                title="插入到光标处"
                className="rounded p-1 text-[12px] text-neutral-400 hover:bg-neutral-100 hover:text-brand-600"
              >
                插入↓
              </button>
              <button
                onClick={() => onDelete(i)}
                title="从文章中删除"
                className="rounded p-1 text-[12px] text-neutral-400 hover:bg-neutral-100 hover:text-red-500"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div className="shrink-0 border-t border-neutral-200 p-2 flex gap-2">
        <button
          onClick={openLibrary}
          disabled={!paperId}
          className="flex-1 rounded-lg border border-neutral-200 px-2 py-1.5 text-[12px] text-neutral-600 hover:border-brand-300 disabled:cursor-not-allowed disabled:text-neutral-300"
          title={paperId ? "从论文图库添加" : "本文章没有关联论文"}
        >
          + 从论文图库
        </button>
        <button
          onClick={() => fileRef.current?.click()}
          className="flex-1 rounded-lg border border-neutral-200 px-2 py-1.5 text-[12px] text-neutral-600 hover:border-brand-300"
        >
          + 上传图片
        </button>
        <input
          ref={fileRef}
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onUpload(f);
            if (fileRef.current) fileRef.current.value = "";
          }}
        />
      </div>

      {libraryOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-neutral-900/40 p-6">
          <div className="flex max-h-[80vh] w-full max-w-3xl flex-col overflow-hidden rounded-xl bg-white shadow-xl">
            <div className="flex items-center gap-2 border-b border-neutral-200 px-4 py-3">
              <span className="text-[14px] font-semibold text-neutral-800">从论文图库添加</span>
              <span className="flex-1" />
              <button
                onClick={() => setLibraryOpen(false)}
                className="text-neutral-400 hover:text-neutral-700"
              >
                ×
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto p-4">
              {loading && <p className="text-[12px] text-neutral-400">加载中…</p>}
              {!loading && figures.length === 0 && (
                <p className="text-[12px] text-neutral-400">没有可添加的图片。</p>
              )}
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                {figures.map((f) => (
                  <button
                    key={f.id}
                    onClick={() => {
                      onAdd(f.image_path, f.caption || altOf(images.length));
                      setLibraryOpen(false);
                    }}
                    className="overflow-hidden rounded-lg border border-neutral-200 text-left hover:border-brand-400"
                  >
                    <img
                      src={fileUrl(f.image_path)}
                      alt={f.caption || "figure"}
                      className="h-28 w-full bg-neutral-50 object-contain"
                    />
                    <span className="block truncate px-2 py-1 text-[11px] text-neutral-500">
                      {f.figure_number != null ? `Figure ${f.figure_number}` : "Figure"}
                      {f.page != null ? ` · 第 ${f.page} 页` : ""}
                      {f.caption ? ` · ${f.caption}` : ""}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: 接入编辑器页**

Modify `frontend/app/articles/[id]/edit/page.tsx`：

import 区追加：

```tsx
import { ArticleImagePanel } from "@/components/ArticleImagePanel";
import { appendImage, insertImageAtCursor, moveImage, removeImage } from "@/lib/articleImages";
```

把 `apiDeleteCover, apiGet, apiPatch, apiPost, apiUploadCover, fileUrl` 的 import 里补上 `apiUploadArticleImage`。

组件内状态区追加（放在 `previewWidth` 附近）：

```tsx
  // ——— 左栏 Tab 与图片管理：正文光标位置用于「插入到光标处」 ———
  const [leftTab, setLeftTab] = useState<"outline" | "images">("outline");
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const cursorRef = useRef<{ start: number; end: number }>({ start: 0, end: 0 });

  function rememberCursor(e: React.SyntheticEvent<HTMLTextAreaElement>) {
    const ta = e.currentTarget;
    cursorRef.current = { start: ta.selectionStart, end: ta.selectionEnd };
  }

  function focusAt(cursor: number) {
    requestAnimationFrame(() => {
      const ta = textareaRef.current;
      if (ta) {
        ta.focus();
        ta.setSelectionRange(cursor, cursor);
      }
    });
  }

  async function persistImages(nextImages: string[], nextContent?: string) {
    setArticle((a) => (a ? { ...a, images: nextImages } : a));
    if (nextContent !== undefined) setContent(nextContent);
    try {
      await apiPatch(
        `/articles/${id}`,
        nextContent !== undefined
          ? { images: nextImages, content: nextContent }
          : { images: nextImages }
      );
    } catch (e) {
      flash(`图片保存失败: ${e}`);
    }
  }

  function handleImageReorder(from: number, to: number) {
    void persistImages(moveImage(article?.images || [], from, to));
  }

  function handleImageDelete(index: number) {
    const { content: nextContent, images: nextImages } = removeImage(
      content,
      article?.images || [],
      index
    );
    void persistImages(nextImages, nextContent);
  }

  function handleImageInsert(index: number, alt: string) {
    const { content: nextContent, cursor } = insertImageAtCursor(
      content,
      cursorRef.current.start,
      cursorRef.current.end,
      index,
      alt
    );
    setContent(nextContent);
    void apiPatch(`/articles/${id}`, { content: nextContent });
    focusAt(cursor);
  }

  function handleImageAdd(key: string, alt: string) {
    const { images: nextImages, index } = appendImage(article?.images || [], key);
    const { content: nextContent, cursor } = insertImageAtCursor(
      content,
      cursorRef.current.start,
      cursorRef.current.end,
      index,
      alt
    );
    void persistImages(nextImages, nextContent);
    flash("已插入到光标处");
    focusAt(cursor);
  }

  async function handleImageUpload(file: File) {
    try {
      const updated = await apiUploadArticleImage(id, file);
      setArticle(updated);
      const nextImages = updated.images || [];
      const index = nextImages.length - 1;
      if (index < 0) return;
      const alt = file.name.replace(/\.[^.]+$/, "") || `Figure ${index + 1}`;
      const { content: nextContent, cursor } = insertImageAtCursor(
        content,
        cursorRef.current.start,
        cursorRef.current.end,
        index,
        alt
      );
      setContent(nextContent);
      await apiPatch(`/articles/${id}`, { content: nextContent });
      flash("已上传并插入到光标处");
      focusAt(cursor);
    } catch (e) {
      alert(`图片上传失败: ${e}`);
    }
  }
```

把原来的左栏 `<aside className="w-52 shrink-0 border-r border-neutral-200 bg-white overflow-y-auto">…</aside>` 整块替换为：

```tsx
        <aside className="w-60 shrink-0 border-r border-neutral-200 bg-white flex flex-col min-h-0">
          <div className="flex shrink-0 border-b border-neutral-200 text-[12px]">
            <button
              onClick={() => setLeftTab("outline")}
              className={`flex-1 py-2 ${
                leftTab === "outline"
                  ? "font-medium text-brand-600 border-b-2 border-brand-500"
                  : "text-neutral-500"
              }`}
            >
              结构
            </button>
            <button
              onClick={() => setLeftTab("images")}
              className={`flex-1 py-2 ${
                leftTab === "images"
                  ? "font-medium text-brand-600 border-b-2 border-brand-500"
                  : "text-neutral-500"
              }`}
            >
              图片 {(article?.images || []).length}
            </button>
          </div>
          {leftTab === "outline" ? (
            <nav className="flex-1 min-h-0 overflow-y-auto pb-4">
              {outline.map((o, i) => (
                <div
                  key={i}
                  className="px-4 py-1 text-[12px] truncate text-neutral-500"
                  style={{ paddingLeft: `${8 + o.level * 8}px` }}
                >
                  {o.text}
                </div>
              ))}
            </nav>
          ) : (
            <ArticleImagePanel
              images={article?.images || []}
              paperId={article?.paper_id || null}
              onReorder={handleImageReorder}
              onDelete={handleImageDelete}
              onInsert={handleImageInsert}
              onAdd={handleImageAdd}
              onUpload={handleImageUpload}
            />
          )}
        </aside>
```

给正文 textarea 加 `ref` 与光标记忆：

```tsx
            <textarea
              ref={textareaRef}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              onSelect={rememberCursor}
              onKeyUp={rememberCursor}
              onClick={rememberCursor}
              onBlur={rememberCursor}
              className="flex-1 resize-none px-6 py-4 font-mono text-[13px] leading-relaxed focus:outline-none"
              placeholder="Markdown 正文…"
            />
```

- [ ] **Step 4: 类型检查 + 单测**

Run: `cd frontend && npx tsc --noEmit && npm test`
Expected: tsc 无输出；`npm test` 全部 PASS。

- [ ] **Step 5: 手工验证（全栈）**

按 `memory/testing.md` 的方式起 WSL docker + Windows 后端，然后用无头 Chrome：

1. 打开一篇有 YOLO 图的文章编辑器 → 左栏切到「图片」→ 拖拽换序，右侧预览对应位置换图；刷新后顺序保持。
2. 删除中间一张 → 后面 `{{figure:N}}` 自动前移、无悬空；「+ 从论文图库」选一张、「+ 上传图片」传一张 → 占位符立即出现在光标处。
3. 正文粘贴样例公式 → 右栏预览 KaTeX 正常排版（列表项内正常）。
4. Mock 模式「发送到草稿箱」→ 任务成功；检查生成 HTML 里公式是 `<img>`。

- [ ] **Step 6: 提交**

```bash
git add frontend/lib/api.ts frontend/components/ArticleImagePanel.tsx frontend/app/articles/[id]/edit/page.tsx
git commit -m "feat(frontend): 文章编辑器左栏图片管理（排序/增删/插到光标）"
```

---

## Self-Review

**Spec coverage:**

- 1.1 数据与接口 → Task 2（`ArticleUpdateRequest.images`、`POST /articles/{id}/images`、复用 figures 接口由 Task 8 的 `openLibrary` 调用）。
- 1.2 纯逻辑 → Task 1。
- 1.3 UI（左栏 Tab / 拖拽 / 删除 / 新增即刻插入 / 图库 Modal / 空态 / alt 优先级）→ Task 8。
- 1.4 边界（`images` 为 null、越界、重复 key、上传失败、立即 PATCH）→ Task 1 测试 + Task 2/7 实现。
- 2.1 公式语法 → Task 3（`INLINE_MATH_RE` / `_MATH_RE` / `_strip_code`）与 Task 6（`INLINE_MATH_RE` / `CODE_HTML_RE`），规则逐条对应；前后端一致性由 Task 7 的共享夹具锁定。
- 2.2 前端预览（依赖注入 / 块级 / KaTeX / CSS / 无 renderMath 兼容）→ Task 6。
- 2.3 后端发布（matplotlib 依赖 / math.py / renderer math_map / `_upload_math_images` / Redis 缓存 / `build_article_payload`）→ Task 3、4、5。
- 2.4 取舍、2.5 边界（代码内 `$` 跳过、块级围栏在代码块之后、失败降级、Redis 异常忽略）→ Task 3/4/5/6 实现与测试。
- 测试清单 → Task 1/2/3/4/5/6/7 的测试文件 + Task 8 手工验证。

**已知不在本计划内的取舍：** 公式不参与「跨公式的加粗/斜体嵌套」（`**$x$**` 仍可用，因为公式替换在加粗之后，不影响）；公式内容含 `*` 且成对出现时可能被斜体规则截断（用户样例不含该情况）。

**类型一致性检查：**

- `moveImage / removeImage / appendImage / insertImageAtCursor` 在 Task 1 定义，Task 8 按同名同签名使用。
- `_image_ext / _append_image` 在 Task 2 定义并在测试与接口中使用。
- `normalize_tex / extract_math / render_math_png` 在 Task 3 定义，Task 4/5 使用；`math_map` 的 key 统一为 `normalize_tex(tex)`。
- `render_markdown_html(md, theme, image_map, math_map)` 第 4 个位置参数在 Task 4 定义，Task 5 的 `build_article_payload` 按位置传入。
- `RenderOptions.renderMath` 在 Task 6 定义并由 `WeChatPreview` 注入；Task 7 用同一 `renderMath` 捕获前端识别的公式，与后端 `extract_math` 对同一夹具比对。
