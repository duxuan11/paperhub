# 文章编辑器：图片管理与公式渲染 — 设计

日期：2026-10-08
状态：已确认
分支：`feat/article-editor-figures-math`

## 背景

两个已确认的问题，都出在「文章编辑器」这条链路上（`frontend/app/articles/[id]/edit/page.tsx`）。

### 1. 图片无法编辑

- `Article.images` 是图片 key 数组（来自论文 figures，含 YOLO 检测图，见 `backend/app/services/article.py` 里 `images=[f.image_path for f in figures]`）。
- 正文用 `![Figure N]({{figure:INDEX}})` 占位，渲染时按下标取 `images[INDEX]`（前端 `resolveFigures`、后端 `render_markdown_html` 的 `image_map`）。
- 编辑器**没有任何图片管理 UI**：`resolveFigures` 只做只读解析，`ArticleUpdateRequest` 也不接受 `images` 字段，用户无法排序 / 增 / 删。
- 痛点：YOLO 检测图的顺序不一定对，导致 `{{figure:N}}` 指向了错误的图，用户无法在编辑器里修正。

### 2. 公式无法渲染

- 编辑器右侧「微信公众号预览」走 `renderWechatHtml`（`frontend/lib/wechatTheme.ts`），只做 escape + 图片/链接/加粗/斜体/行内代码，**完全不处理 `$...$`**。
- 后端 `publishers/wechat/renderer.py` 同样不处理，所以 `$X = [\alpha, h_m, l_h, g_{ext}]$` 这类内容在预览和发布里都是源码文字。
- 论文阅读页的 `Markdown.tsx` 有 remark-math + rehype-katex，是唯一能正常渲染的入口，与文章编辑器无关。
- 微信正文只接受 inline style HTML，无法加载 KaTeX 的 CSS / 字体，因此「把 KaTeX 输出塞进公众号正文」在微信里不可行；要在微信里正确显示公式，必须把公式转成图片走 `media/uploadimg`。

## 目标与非目标

目标：

- 编辑器可对文章图片**排序（修正顺序）/ 新增 / 删除**，并且改动即时反映到右侧预览与最终发布。
- 新增图片后立刻插入到正文光标处。
- 编辑器右侧预览能正确渲染 `$...$`（含列表项、表格单元格、标题、图注内的行内公式）与块级 `$$...$$`。
- 发布到公众号时公式同样正确显示（转图片上传）。

非目标：

- 不改图片占位符语法，仍是 `{{figure:N}}`；不改 `Article.images` 的数据类型。
- 不做图片裁剪 / 旋转 / 替换内容，只做排序 / 增 / 删。
- 不自动改写 `![...]` 里的图注文字（删除时只动占位符本身）。
- 不做公式的可视化编辑器 / 插入面板。
- 不改阅读页（remark-math 已正常）。
- 不追求预览（KaTeX）与发布（matplotlib）的像素级一致。

## 设计

### 1. 图片管理

#### 1.1 数据与接口

- `backend/app/schemas.py` 的 `ArticleUpdateRequest` 增加 `images: list[str] | None = None`，让 PATCH 能持久化排序 / 增 / 删后的列表。现有 `update_article` 用 `model_dump(exclude_unset=True)` + `setattr`，无需额外改动。
- 新增 `POST /api/v1/articles/{id}/images`（multipart）：
  - 校验沿用封面那套（PNG / JPG / WEBP / GIF，≤10MB），把 `_cover_ext` 抽成可复用 helper（如 `_image_ext`）；
  - 存对象存储 `articles/{id}/images/{uuid}{ext}`；
  - `art.images` 为 `None` 时先置 `[]`，再 append；
  - 返回更新后的 `ArticleOut`。
- 「从论文图库添加」复用现有 `GET /api/v1/papers/{paper_id}/figures`（`FigureOut`：`image_path/caption/figure_number/page/type`），前端过滤掉 `image_path` 已在 `article.images` 中的项。文章无 `paper_id` 时该入口置灰。

#### 1.2 纯逻辑（新增 `frontend/lib/articleImages.ts`，可单测）

- `moveImage(images, from, to) -> string[]`：只重排数组，**不改正文**（换图不换位），用于修正 YOLO 顺序。
- `removeImage(content, images, index) -> { content, images }`：
  - 从 `images` 删除 `images[index]`；
  - 扫描正文 `{{figure:N}}`：`N === index` 时，若该占位符构成独占一行的 `![...]({{figure:N}})` 则删掉整行并收敛多余空行，否则只删掉占位符本身；`N > index` 改写为 `{{figure:N-1}}`；`N < index` 不动。
- `appendImage(images, key) -> { images, index }`：append 并返回新下标。
- `insertImageAtCursor(content, selectionStart, selectionEnd, index, alt) -> { content, cursor }`：用 `\n![alt]({{figure:N}})\n` 替换选区，返回新正文与新光标位。

#### 1.3 UI（左栏 Tab）

编辑器左栏由固定「文章结构」改为两个 Tab：**「结构」/「图片 (N)」**，宽度 `w-52` → `w-60`。

```
[ 结构 ] [ 图片 5 ]
┌──────────────────────────┐
│ ⠿ #1  [缩略图]  插入↓ 删除× │  ← 拖拽排序
│ ⠿ #2  [缩略图]  插入↓ 删除× │
│ …                        │
├──────────────────────────┤
│ + 从论文图库   + 上传图片 │
└──────────────────────────┘
```

- **排序**：HTML5 拖拽（`⠿` 手柄），成功后立即 `PATCH {images}`。预览按下标取图，会自动刷新。
- **删除**：`removeImage` 后一次 `PATCH {images, content}`（重编号后的正文必须同批落库）。
- **新增**：选图 / 上传成功 → `appendImage` → **立刻在光标处插入占位符**（`insertImageAtCursor`）→ 一次性 `PATCH {images, content}`，flash「已插入到光标处」。插入位置取打开文件选择框 / 点选图库项之前记录的 `selectionStart/End`。
- 「从论文图库」是居中 Modal：缩略图网格 + 图注 + 页码，点选即加入。
- Tab 上显示图片数量；空态提示「暂无图片，可从论文图库添加或上传」。
- `alt` 取值优先级：`Figure.caption` → `Figure N` → 文件名。

#### 1.4 边界与异常

- `article.images` 为 `null`：视作 `[]`。
- 正文中的 `{{figure:N}}` 越界不会崩：`resolveFigures` / `image_map` 取不到就回退 `#`（现状行为），删除时按 `1.2` 的规则处理。
- 同一 key 在 `images` 里出现两次：按项处理，删除只删该下标一项。
- 上传失败 / 超限：alert 提示，不改本地状态。
- 未保存即离开：图片操作会立即 PATCH，不依赖「保存草稿」；标题 / 正文的普通编辑仍走原保存流程。

### 2. 公式渲染

#### 2.1 统一公式语法（前后端各实现一份，规则一致）

- **行内**：`$...$`。起始 `$` 后不能是空白，结束 `$` 前不能是空白，内容不含换行、不含反引号（避免与行内代码冲突）；`\$` 为转义字面量。
- **块级**：独占一行的 `$$...$$`，或 `$$` 围栏跨多行。
- 其余 `$`（如价格 `$100`）保持字面量。

#### 2.2 前端预览（复用现渲染器 + 依赖注入）

- `RenderOptions` 新增可选 `renderMath?: (tex: string, display: boolean) => string`。
- `wechatTheme.ts` 的 `inline()` 先按 2.1 切段：非公式段走现有 escape / 加粗 / 斜体 / 链接 / 行内代码逻辑，公式段交给 `renderMath`；块级公式在 `renderWechatHtml` 主循环里单独产出一个居中容器。
- 列表项 / 表格单元格 / 标题 / 图注都经过 `inline()`，因此全覆盖。
- `WeChatPreview` 注入 KaTeX 实现：`katex.renderToString(tex, { displayMode, throwOnError: false, strict: false })`，并显式 `import "katex/dist/katex.min.css"`（仅供本地预览；发布链路不用它）。
- 不传 `renderMath`（node 单测、主题未加载退回 `Markdown`）时行为与今天完全一致：`$...$` 原样显示 → 向后兼容。

#### 2.3 后端发布（matplotlib → PNG → 上传微信）

- `backend/pyproject.toml` 新增 core dependency `matplotlib`（惰性 import，仅发布链路渲染用）。
- 新增 `publishers/wechat/math.py`：
  - `normalize_tex(tex) -> str`：常见宏归一化（`\ge→\geq`、`\le→\leq`、`\ne→\neq`、`\to→\rightarrow` 等）。spike 已确认 matplotlib mathtext 不认识 `\ge`；`°`、`\mu`、下标、`\frac`、`\text` 可直接用。
  - `extract_math(md) -> list[str]`：按 2.1 语法取出**去重后**的公式（保留首次出现顺序）。
  - `render_math_png(tex, display=False, size_px=16) -> bytes | None`：Agg 后端渲染透明底 PNG；行内按正文字号（≈1em 高），块级居中放大；失败返回 `None`。worker 从 `theme_obj.css("paragraph")["font-size"]` 解析出 px 传入，解析失败用 16。
- `render_markdown_html(md, theme, image_map, math_map)`：`math_map = {归一化 tex: 微信图片 URL}`。命中 → 输出 `<img>`（行内 `vertical-align:middle`，块级居中）；未命中 → 退化为转义后的 `$...$` 原文（今天的行为），并记日志。
- Worker（`backend/app/workers/tasks.py`）新增 `_upload_math_images(publisher, content) -> dict[str, str]`：
  - 按 `sha1(normalize_tex(tex))` 查 Redis 缓存（`wechat:math:{hash}` → mmbiz URL），命中直接复用；
  - 未命中：`render_math_png` → `publisher.upload_content_image(png, f"math-{hash[:8]}.png")` → 回写缓存；
  - 渲染失败：跳过该条（渲染器自动降级为原文），并记 warning。
- `publish_wechat_article` 里与 `_upload_content_images` 并列调用；`build_article_payload(..., math_map=...)` 透传到 `render_markdown_html`。

#### 2.4 已知取舍

- 预览用 KaTeX、发布用 matplotlib，**视觉上都是数学排版但像素级不完全一致**（已确认接受）。
- matplotlib 是 Python 侧不依赖 LaTeX 工具链的务实选择；少数不支持的公式（如 `\begin{align}`）发布会降级为原文。
- 若后续要求像素级一致，可另开分支把预览也切成图片渲染。

#### 2.5 边界与异常

- 行内代码 `` `...` `` 内的 `$` 不视为公式（2.1 已用「内容不含反引号」约束）。
- 代码围栏内的 `$$` 不处理：`renderWechatHtml` / `render_markdown_html` 的代码块分支在块级公式判断之前。
- KaTeX 渲染失败：`throwOnError:false`，出错公式以 KaTeX 的 errorColor 显示，不中断其余渲染。
- 发布侧公式渲染失败：正文里保留 `$...$` 原文（用户至少能看到公式内容），不影响草稿创建。
- 未配置 Redis / 缓存读写异常：忽略缓存，照常渲染上传（与封面 media_id 缓存同一处理方式）。

## 测试

前端：

- 新增 `frontend/tests/articleImages.test.mjs`：`moveImage` 返回重排后的新数组且不改动入参、`removeImage` 删除并重编号（独占行 / 内联两种）、越界与重复 key、`insertImageAtCursor` 的选区替换与光标位。
- 新增 `frontend/tests/wechatMath.test.mjs`：用 stub `renderMath` 验证 `renderWechatHtml` 的公式切段（段落 / 列表项 / 表格单元格 / 标题）、块级 `$$` 居中容器、`$100` 与代码内 `$` 不被当公式、不传 `renderMath` 时输出与旧行为一致（原文保留）。
- 把两个新测试加入 `frontend/package.json` 的 `test` 脚本；`npx tsc --noEmit`。

后端：

- 新增 `backend/tests/test_wechat_math.py`：`normalize_tex`、`extract_math`（去重 / 忽略价格 / 忽略代码块）、`render_math_png` 对用户示例公式产出非空 PNG、`render_markdown_html` 在有 / 无 `math_map` 时的 `<img>` 与降级行为。
- 新增 `backend/tests/test_article_images.py`：`POST /articles/{id}/images` 追加并返回 `ArticleOut`、类型 / 大小校验、`PATCH {images}` 持久化排序结果。
- `backend/tests/test_wechat_publish.py` 补一条：正文含 `$...$` 时 `build_article_payload` 的 HTML 含公式 `<img>`。
- `uv run pytest -q`。

手工验证：

1. 打开有 YOLO 图的文章 → 左栏「图片」Tab 拖拽换序 → 右侧预览对应位置换图；保存后刷新仍保持。
2. 删除中间一张 → 后面 `{{figure:N}}` 自动前移、无悬空引用；从图库新增 + 上传各一次 → 占位符立即插到光标处。
3. 正文粘贴用户给的公式样例 → 右栏预览 KaTeX 正常排版（列表项内也正常）。
4. Mock 模式发送草稿 → 任务成功；查看生成的 HTML，公式为 `<img>`。

## 影响文件

前端：

- `frontend/lib/wechatTheme.ts`（公式切段 + 块级渲染）
- `frontend/components/WeChatPreview.tsx`（注入 KaTeX）
- `frontend/app/articles/[id]/edit/page.tsx`（左栏 Tab、拖拽、增删、光标签入）
- 新增 `frontend/lib/articleImages.ts`
- 新增 `frontend/tests/articleImages.test.mjs`、`frontend/tests/wechatMath.test.mjs`
- `frontend/package.json`（test 列表）

后端：

- `backend/app/schemas.py`（`ArticleUpdateRequest.images`）
- `backend/app/api/v1/articles.py`（`POST /{id}/images`）
- `backend/pyproject.toml`（`matplotlib`）
- 新增 `publishers/wechat/math.py`
- `publishers/wechat/renderer.py`（`math_map`）
- `publishers/wechat/publisher.py`（`build_article_payload` 透传 `math_map`）
- `backend/app/workers/tasks.py`（`_upload_math_images` + 发布链路接线）
- 新增 `backend/tests/test_wechat_math.py`、`backend/tests/test_article_images.py`
- `backend/tests/test_wechat_publish.py`（补公式用例）
