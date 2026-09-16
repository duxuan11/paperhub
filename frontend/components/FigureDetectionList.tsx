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
