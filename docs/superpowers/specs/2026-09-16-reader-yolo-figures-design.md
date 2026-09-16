# 阅读页末尾展示 YOLO 检测图 — 设计

日期：2026-09-16
状态：已确认

## 背景

Pipeline 现状（`backend/app/workers/tasks.py`）：

- `parse_paper` 调 MinerU，成功后把状态置为 `PARSED`，并**自动**创建/投递 `detect_figures` 任务（tasks.py:105-114）。
- `detect_figures` 若配置了 `yolo_enabled` + `yolo_model_path` 且能读到 PDF，则 `OnnxYoloService` 整页渲染 + YOLO 检测，裁剪图存到 `{paper_id}/figures/pageX_figN.png`（tasks.py:146-152）；YOLO 未配置/检测为空/异常时回退 `HeuristicFigureService`，图沿用 MinerU 的 `{paper_id}/images/...`。
- AI 分析（`services/analysis.py`）与 YOLO 无关，只消费 MinerU 的 markdown/figures。

阅读页现状（`frontend/app/papers/[id]/page.tsx`）：

- 已拉取 `/papers/{id}/figures` 到 `figures` state，并 4s 轮询。
- 左侧目录只用文字列出 `Figure N`，不可点击，也不显示图片。
- 正文只渲染 MinerU markdown（`components/Markdown.tsx`，图片经 `fileUrl(paperId + "/" + src)` 解析）。

需求：阅读页在 MinerU markdown **末尾**展示 YOLO 检测图，带 Figure 序号；左侧 Figure 列表可点击跳转。

## 目标与非目标

目标：

- 正文 markdown 之后追加 YOLO 检测图区块，图片带 `Figure N` 编号与页码，点击可打开原图。
- 左侧目录的 Figure 项变为锚点，点击滚动到对应检测图。

非目标：

- 不展示、不重复 MinerU 原始图片（已在正文 markdown 中）。
- 不改后端接口、不改数据库 schema、不改 YOLO/解析流水线。
- 不引入灯箱、懒加载以外的交互（不做分页、不做人工校正编号）。

## 设计

### 数据

无后端改动。前端复用已加载的 `Figure[]`：

- YOLO 图判定：`image_path` 含 `/figures/`（回退图来自 MinerU `images/`，两者路径天然可区分）。
- 排序：按 `figure_number` 升序；`figure_number` 为 null 的项按数组顺序兜底编号（渲染时用递增序号）。
- 图片 URL：`fileUrl(figure.image_path)`（与 `Markdown.tsx` 同一解析方式，走 `/api/v1/files/...`）。
- 刷新：沿用现有 4s 轮询，无需额外请求。

### 正文末尾区块

位置：`<Markdown content={markdown} paperId={id} />` 之后、abstract 占位之前。

仅当存在 YOLO 图时渲染整块（否则不渲染、不提示）：

```
Figure 检测结果（YOLO）              ← h2 视觉风格，复用 .prose-md h2
┌───────────────────────────┐
│  <a href=原图 target=_blank>│
│    <img loading=lazy>      │
│  </a>                      │
└───────────────────────────┘
Figure 1 · 第 3 页                  ← 无 page 时只显示 "Figure 1"
```

- 每张图容器 `id="figure-{n}"`（n 为展示编号），供锚点跳转。
- `<img>` 复用 `.prose-md img`（`max-w-full rounded-lg border border-neutral-200 my-3`），居中显示。
- `figure_number` 为 null 时用递增序号，保证 id 唯一稳定。

### 左侧目录

现有 `figures.length > 0` 的文字块改为：

- 分组标题「Figure 检测」。
- 只列 YOLO 图，每项 `<a href="#figure-{n}">Figure {n}</a>`，样式与上方 TOC 项一致。
- 无 YOLO 图时整个分组不渲染（与正文区块一致，避免"有编号却点不动"）。

### 边界与异常

- 论文未解析 / 无 figures：两个位置都不渲染，页面与现状一致。
- 轮询导致 figures 变化：React 以 id 为 key，区块重渲染，锚点依旧有效。
- 同一编号多张图（YOLO 当前不会产生）：各自独立渲染，caption 编号相同。

## 测试

- `cd frontend && npx tsc --noEmit`（类型）
- `cd frontend && npm test`（node:test）
- 手工验证：
  1. 未配置 YOLO 的论文：正文末尾无区块，左侧无「Figure 检测」分组。
  2. 配置 YOLO 的论文：区块出现，编号/页码正确，点击图片新标签打开原图。
  3. 点击左侧 `Figure N`，滚动到对应图。

## 影响文件

- `frontend/app/papers/[id]/page.tsx`（主要改动）
- 可能新增 `frontend/components/FigureList.tsx`（若抽取区块为独立组件，便于单测）
- 不改后端
