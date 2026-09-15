"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import type { Paper } from "@/lib/types";
import { AIAnalysisPanel } from "@/components/AIAnalysisPanel";
import { StatusBadge } from "@/components/StatusBadge";

/**
 * AI 分析页：为选中的论文配置并执行 Skills 分析。
 *
 * 支持 `?paper=<id>` 深链（论文阅读器「AI 分析」入口会带上当前论文）。
 */
export default function AnalysisPage() {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [paperId, setPaperId] = useState("");
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const wanted = new URLSearchParams(window.location.search).get("paper") || "";
    apiGet<Paper[]>("/papers?limit=200")
      .then((list) => {
        setPapers(list);
        const valid = list.some((p) => p.id === wanted);
        setPaperId(valid ? wanted : list[0]?.id || "");
      })
      .catch(() => setPapers([]))
      .finally(() => setLoaded(true));
  }, []);

  const current = papers.find((p) => p.id === paperId) || null;

  return (
    <div className="h-full flex flex-col">
      <div className="px-6 py-3 bg-white border-b border-neutral-200 shrink-0 flex items-center gap-3">
        <h1 className="text-[15px] font-semibold text-neutral-900">AI 分析</h1>
        <div className="flex-1" />
        {papers.length > 0 && (
          <>
            <label className="text-[12px] text-neutral-400">选择论文</label>
            <select
              value={paperId}
              onChange={(e) => setPaperId(e.target.value)}
              className="max-w-[420px] px-3 py-1.5 rounded-lg border border-neutral-200 text-[12px] text-neutral-700 focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
            >
              {papers.map((p) => (
                <option key={p.id} value={p.id}>
                  {(p.title || p.filename || p.id).slice(0, 80)}
                </option>
              ))}
            </select>
            <StatusBadge status={current?.status || ""} />
          </>
        )}
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto bg-neutral-50">
        {paperId ? (
          <AIAnalysisPanel key={paperId} paperId={paperId} />
        ) : (
          <div className="text-[13px] text-neutral-400 py-24 text-center">
            {loaded ? "论文库为空，请先上传论文。" : "正在加载论文…"}
          </div>
        )}
      </div>
    </div>
  );
}
