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
