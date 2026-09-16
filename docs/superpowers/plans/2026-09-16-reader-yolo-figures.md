# 阅读页末尾展示 YOLO 检测图 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 论文阅读页在 MinerU markdown 末尾展示 YOLO 检测裁剪图（带 Figure 编号与页码），并让左侧目录的 Figure 项可点击跳转。

**Architecture:** 纯前端改动。新增 `frontend/lib/figures.ts` 存纯逻辑（筛选 YOLO 图 / 排序 / 生成锚点 id），用 node:test 单测；新增 `frontend/components/FigureDetectionList.tsx` 只负责渲染区块；`frontend/app/papers/[id]/page.tsx` 接线（正文末尾 + 左侧锚点）。后端、DB、流水线均不改。

**Tech Stack:** Next.js 15 App Router（client component）、React 19、TypeScript 5.7、Tailwind、node:test（`node --experimental-strip-types --test`）。

## Global Constraints

- 不做后端改动，不改数据库 schema，不改 YOLO / MinerU 流水线。
- YOLO 图判定：`figure.image_path` 含 `/figures/`（MinerU 回退图为 `{paper_id}/images/...`）。
- 只展示 YOLO 图；无 YOLO 图时正文区块与左侧分组都不渲染。
- 图片 URL 一律用 `fileUrl()`（`frontend/lib/api.ts:74`，即 `/api/proxy/files/{encodeURIComponent(key)}`）。
- 测试遵循现有模式：纯逻辑放 `frontend/lib/*.ts`，测试放 `frontend/tests/*.test.mjs`，用 `import ... from "../lib/<name>.ts"`；`package.json` 的 `test` 脚本显式列出测试文件（新文件要加进去）。
- 验证命令：`cd frontend && npx tsc --noEmit` 与 `cd frontend && npm test`。

---

### Task 1: YOLO 检测图纯逻辑 + 单测

**Files:**
- Create: `frontend/lib/figures.ts`
- Test: `frontend/tests/figures.test.mjs`
- Modify: `frontend/package.json`（`test` 脚本追加测试文件）

**Interfaces:**
- Consumes: `Figure` 类型（`frontend/lib/types.ts`，字段 `id / figure_number / image_path / caption / bbox / type / page`）。
- Produces:
  - `export interface DisplayFigure { id: string; number: number; imagePath: string; page: number | null }`
  - `export function isYoloFigure(figure: Pick<Figure, "image_path">): boolean`
  - `export function figureAnchorId(sequence: number): string` → `"figure-{sequence}"`
  - `export function yoloFigures(figures: Figure[]): DisplayFigure[]`

- [ ] **Step 1: 写失败的测试**

创建 `frontend/tests/figures.test.mjs`：

```javascript
/**
 * 阅读页 Figure 展示纯逻辑测试（node:test + 类型擦除）。
 *
 * 运行：npm --prefix frontend test
 */

import test from "node:test";
import assert from "node:assert/strict";

import {
  figureAnchorId,
  isYoloFigure,
  yoloFigures,
} from "../lib/figures.ts";

function figure(overrides = {}) {
  return {
    id: "f",
    paper_id: "p1",
    figure_number: 1,
    image_path: "p1/figures/page1_fig1.png",
    caption: null,
    bbox: null,
    type: "figure",
    page: 1,
    created_at: null,
    ...overrides,
  };
}

test("isYoloFigure distinguishes yolo crops from mineru images", () => {
  assert.equal(isYoloFigure(figure()), true);
  assert.equal(
    isYoloFigure(figure({ image_path: "p1/images/abc.jpg" })),
    false
  );
  assert.equal(isYoloFigure(figure({ image_path: "" })), false);
});

test("figureAnchorId builds a stable anchor", () => {
  assert.equal(figureAnchorId(3), "figure-3");
});

test("yoloFigures keeps only yolo crops sorted by figure_number", () => {
  const out = yoloFigures([
    figure({ id: "b", figure_number: 2, image_path: "p1/figures/page2_fig1.png", page: 2 }),
    figure({ id: "md", figure_number: 1, image_path: "p1/images/x.jpg", page: 1 }),
    figure({ id: "a", figure_number: 1, image_path: "p1/figures/page1_fig1.png", page: 1 }),
  ]);
  assert.deepEqual(out, [
    { id: "figure-1", number: 1, imagePath: "p1/figures/page1_fig1.png", page: 1 },
    { id: "figure-2", number: 2, imagePath: "p1/figures/page2_fig1.png", page: 2 },
  ]);
});

test("yoloFigures falls back to sequence when figure_number is null", () => {
  const out = yoloFigures([
    figure({ figure_number: null, page: null, image_path: "p1/figures/a.png" }),
    figure({ figure_number: null, page: 4, image_path: "p1/figures/b.png" }),
  ]);
  assert.deepEqual(
    out.map((f) => [f.id, f.number, f.page]),
    [
      ["figure-1", 1, null],
      ["figure-2", 2, 4],
    ]
  );
});

test("yoloFigures returns empty list when there is no detection", () => {
  assert.deepEqual(yoloFigures([]), []);
  assert.deepEqual(yoloFigures([figure({ image_path: "p1/images/x.jpg" })]), []);
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npm test`
Expected: FAIL — `Cannot find module '../lib/figures.ts'`（或 `ERR_MODULE_NOT_FOUND`）

- [ ] **Step 3: 实现最小代码**

创建 `frontend/lib/figures.ts`：

```typescript
/**
 * 阅读页 Figure 展示纯逻辑（与 UI 解耦，便于 node:test 直接测试）。
 *
 * YOLO 整页检测的裁剪图存于 `{paper_id}/figures/...`；
 * md 回退的图沿用 MinerU 的 `{paper_id}/images/...`，两者路径可区分。
 */

import type { Figure } from "./types.ts";

export interface DisplayFigure {
  /** 锚点 id：`figure-{sequence}`，正文 figure 与左侧目录共用。 */
  id: string;
  /** 展示编号：优先 DB 的 figure_number，缺失时按顺序兜底。 */
  number: number;
  imagePath: string;
  page: number | null;
}

export function isYoloFigure(figure: Pick<Figure, "image_path">): boolean {
  return (figure.image_path || "").includes("/figures/");
}

export function figureAnchorId(sequence: number): string {
  return `figure-${sequence}`;
}

/** 取出 YOLO 检测图，按 figure_number 升序，序号缺失时按原顺序兜底。 */
export function yoloFigures(figures: Figure[]): DisplayFigure[] {
  const yolo = (figures || []).filter(isYoloFigure);
  const sorted = [...yolo].sort(
    (a, b) => (a.figure_number ?? 0) - (b.figure_number ?? 0)
  );
  return sorted.map((f, i) => {
    const sequence = i + 1;
    return {
      id: figureAnchorId(sequence),
      number: f.figure_number ?? sequence,
      imagePath: f.image_path,
      page: f.page ?? null,
    };
  });
}
```

- [ ] **Step 4: 把测试文件加入 npm test 脚本**

修改 `frontend/package.json` 的 `scripts.test`（原值：`node --experimental-strip-types --test tests/themeConfig.test.mjs tests/aiAnalysis.test.mjs`）：

```json
"test": "node --experimental-strip-types --test tests/themeConfig.test.mjs tests/aiAnalysis.test.mjs tests/figures.test.mjs"
```

Run: `cd frontend && npm test`
Expected: PASS — 5 个新用例通过，旧的 themeConfig / aiAnalysis 用例仍通过

- [ ] **Step 5: 类型检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无错误输出

- [ ] **Step 6: 提交**

```bash
git add frontend/lib/figures.ts frontend/tests/figures.test.mjs frontend/package.json
git commit -m "feat(frontend): 阅读页 YOLO 检测图展示纯逻辑"
```

---

### Task 2: 检测图区块组件

**Files:**
- Create: `frontend/components/FigureDetectionList.tsx`

**Interfaces:**
- Consumes: `DisplayFigure`、`fileUrl`（`frontend/lib/api.ts:74`）。
- Produces: `export function FigureDetectionList({ figures }: { figures: DisplayFigure[] }): JSX.Element | null` —— `figures` 为空时返回 `null`（不渲染任何节点）。

- [ ] **Step 1: 创建组件**

创建 `frontend/components/FigureDetectionList.tsx`：

```tsx
"use client";

import { fileUrl } from "@/lib/api";
import type { DisplayFigure } from "@/lib/figures";

/** MinerU markdown 末尾的 YOLO 检测图区块；无检测结果时不渲染。 */
export function FigureDetectionList({ figures }: { figures: DisplayFigure[] }) {
  if (figures.length === 0) return null;

  return (
    <section className="mt-10 pt-6 border-t border-neutral-200">
      <h2 className="text-xl font-semibold mb-3 text-neutral-900">
        Figure 检测结果（YOLO）
      </h2>
      <div className="space-y-6">
        {figures.map((f) => (
          <figure key={f.id} id={f.id} className="scroll-mt-4">
            <a href={fileUrl(f.imagePath)} target="_blank" rel="noreferrer">
              <img
                src={fileUrl(f.imagePath)}
                alt={`Figure ${f.number}`}
                loading="lazy"
                className="max-w-full rounded-lg border border-neutral-200 my-2 mx-auto"
              />
            </a>
            <figcaption className="text-center text-[12px] text-neutral-500">
              Figure {f.number}
              {f.page ? ` · 第 ${f.page} 页` : ""}
            </figcaption>
          </figure>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 2: 类型检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无错误输出

- [ ] **Step 3: 提交**

```bash
git add frontend/components/FigureDetectionList.tsx
git commit -m "feat(frontend): YOLO 检测图区块组件"
```

---

### Task 3: 阅读页接线（正文末尾区块 + 左侧锚点）

**Files:**
- Modify: `frontend/app/papers/[id]/page.tsx`（import 区、`yoloFigures` memo、左侧 aside 的 figures 块、`<article>` 内 Markdown 之后）

**Interfaces:**
- Consumes: `yoloFigures`（Task 1）、`FigureDetectionList`（Task 2）。
- Produces: 无（终端 UI 改动）。

- [ ] **Step 1: 引入依赖与 memo**

在 `frontend/app/papers/[id]/page.tsx` 顶部 import 区，把：

```tsx
import { Markdown } from "@/components/Markdown";
import { ChatPanel } from "@/components/ChatPanel";
import { StatusBadge } from "@/components/StatusBadge";
```

改为：

```tsx
import { Markdown } from "@/components/Markdown";
import { FigureDetectionList } from "@/components/FigureDetectionList";
import { ChatPanel } from "@/components/ChatPanel";
import { StatusBadge } from "@/components/StatusBadge";
import { yoloFigures } from "@/lib/figures";
```

并在 `const toc = useMemo(() => extractToc(markdown), [markdown]);` 之后新增：

```tsx
  const detectedFigures = useMemo(() => yoloFigures(figures), [figures]);
```

- [ ] **Step 2: 左侧目录改成锚点**

把左侧 aside 中现有的：

```tsx
            {figures.length > 0 && (
              <div className="mt-3 pt-3 border-t border-neutral-100">
                {figures.map((f) => (
                  <div key={f.id} className="px-4 py-1 text-[11px] text-neutral-400">
                    Figure {f.figure_number}
                  </div>
                ))}
              </div>
            )}
```

替换为：

```tsx
            {detectedFigures.length > 0 && (
              <div className="mt-3 pt-3 border-t border-neutral-100">
                <div className="px-4 py-1 text-[11px] font-medium text-neutral-400">
                  Figure 检测
                </div>
                {detectedFigures.map((f) => (
                  <a
                    key={f.id}
                    href={`#${f.id}`}
                    className="block px-4 py-1 text-[12px] truncate text-neutral-500 hover:bg-neutral-50 hover:text-brand-600"
                  >
                    Figure {f.number}
                  </a>
                ))}
              </div>
            )}
```

- [ ] **Step 3: 正文末尾追加区块**

把 `<article>` 中的：

```tsx
            {markdown ? (
              <Markdown content={markdown} paperId={id} />
            ) : (
```

改为：

```tsx
            {markdown ? (
              <>
                <Markdown content={markdown} paperId={id} />
                <FigureDetectionList figures={detectedFigures} />
              </>
            ) : (
```

- [ ] **Step 4: 类型检查 + 单测**

Run: `cd frontend && npx tsc --noEmit && npm test`
Expected: 两者均无错误（`npm test` 全部用例 PASS）

- [ ] **Step 5: 手工验证（无 YOLO 配置的论文）**

启动前后端（`make dev` 或 `cd frontend && npm run dev`），打开一篇未配置 YOLO 的论文阅读页。
Expected: 正文末尾无「Figure 检测结果（YOLO）」区块；左侧无「Figure 检测」分组；正文图片正常显示。

- [ ] **Step 6: 手工验证（有 YOLO 配置的论文）**

打开一篇已跑过 YOLO（`image_path` 含 `/figures/`）的论文阅读页。
Expected: 正文末尾出现区块，每张图下方为 `Figure N · 第 X 页`；点击图片在新标签页打开原图；点击左侧 `Figure N` 滚动到对应图。

- [ ] **Step 7: 提交**

```bash
git add "frontend/app/papers/[id]/page.tsx"
git commit -m "feat(frontend): 阅读页末尾展示 YOLO 检测图并支持目录跳转"
```

---

## Self-Review

**Spec coverage：**
- 只展示 YOLO 图（`/figures/` 判定）→ Task 1 `isYoloFigure` / `yoloFigures`。
- 正文末尾区块 + `Figure N · 第 X 页` + 点击开原图 → Task 2、Task 3 Step 3。
- 左侧目录锚点跳转 → Task 3 Step 2。
- 空态不渲染 → Task 2 `if (figures.length === 0) return null` + Task 3 条件渲染。
- `figure_number` 为 null 兜底 → Task 1 用例覆盖。
- 无后端/DB 改动 → 全部任务仅涉及 `frontend/`。

**Placeholder scan：** 无 TBD/TODO；所有步骤含完整代码与命令。

**Type consistency：** `DisplayFigure`（`id / number / imagePath / page`）在 Task 1 定义，Task 2 props、Task 3 `detectedFigures` 用法一致；`figureAnchorId` 命名全篇统一；`fileUrl` 来自现有 `lib/api.ts`。
