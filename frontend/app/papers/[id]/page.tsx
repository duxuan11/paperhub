"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { apiGet, apiPost } from "@/lib/api";
import type { Figure, Job, Paper } from "@/lib/types";
import { Markdown } from "@/components/Markdown";
import { ChatPanel } from "@/components/ChatPanel";
import { StatusBadge } from "@/components/StatusBadge";

interface TocItem {
  level: number;
  text: string;
  id: string;
}

function extractToc(md: string): TocItem[] {
  const items: TocItem[] = [];
  const lines = md.split("\n");
  for (const line of lines) {
    const m = line.match(/^(#{1,4})\s+(.+)$/);
    if (m) {
      items.push({
        level: m[1].length,
        text: m[2].replace(/[*_`]/g, "").trim(),
        id: m[2].trim().toLowerCase().replace(/[^a-z0-9\u4e00-\u9fa5]+/g, "-"),
      });
    }
  }
  return items;
}

const STEPS: { key: string; label: string; match: string[] }[] = [
  { key: "upload", label: "PDF 上传", match: ["UPLOADED"] },
  { key: "parse", label: "MinerU 解析", match: ["PARSING", "PARSED"] },
  { key: "markdown", label: "Markdown", match: ["PARSED"] },
  { key: "figure", label: "Figure 检测", match: ["FIGURE_DETECTING", "READY"] },
  { key: "ai", label: "AI 分析", match: ["ANALYZING", "ANALYZED"] },
  { key: "content", label: "公众号文章", match: ["CONTENT_GENERATED", "PUBLISHED"] },
  { key: "publish", label: "发布", match: ["PUBLISHED"] },
];

export default function PaperReaderPage() {
  const { id } = useParams<{ id: string }>();
  const [paper, setPaper] = useState<Paper | null>(null);
  const [markdown, setMarkdown] = useState("");
  const [figures, setFigures] = useState<Figure[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [activeSection, setActiveSection] = useState("");

  const toc = useMemo(() => extractToc(markdown), [markdown]);

  const load = useCallback(async () => {
    try {
      const [p, md, fig, jb] = await Promise.all([
        apiGet<Paper>(`/papers/${id}`),
        apiGet<{ markdown: string }>(`/papers/${id}/markdown`).catch(() => ({ markdown: "" })),
        apiGet<Figure[]>(`/papers/${id}/figures`).catch(() => []),
        apiGet<Job[]>(`/papers/${id}/jobs`).catch(() => []),
      ]);
      setPaper(p);
      setMarkdown(md.markdown || "");
      setFigures(fig);
      setJobs(jb);
    } catch (e) {
      console.error(e);
    }
  }, [id]);

  useEffect(() => {
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [load]);

  async function run(path: string, label: string) {
    try {
      await apiPost(path);
      setTimeout(load, 1500);
    } catch (e) {
      alert(`${label}失败: ${e}`);
    }
  }

  const status = paper?.status || "";
  const stepDone = (idx: number) => {
    const order = ["UPLOADED", "PARSING", "PARSED", "FIGURE_DETECTING", "READY", "ANALYZING", "ANALYZED", "CONTENT_GENERATED", "PUBLISHED"];
    const cur = order.indexOf(status);
    return cur >= order.indexOf(STEPS[idx].match[0]) || STEPS[idx].match.includes(status);
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-4 px-6 py-3 bg-white border-b border-neutral-200 shrink-0">
        <Link href="/" className="text-neutral-400 hover:text-neutral-600 text-[13px]">
          ← 返回
        </Link>
        <h1 className="text-[15px] font-semibold text-neutral-900 truncate flex-1">
          {paper?.title || paper?.filename || "论文"}
        </h1>
        <StatusBadge status={status} />
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => run(`/papers/${id}/parse`, "解析")}
            className="px-2.5 py-1 rounded-md border border-neutral-200 text-[11px] text-neutral-500 hover:text-brand-600"
          >
            重新解析
          </button>
          <button
            onClick={() => run(`/papers/${id}/detect-figures`, "检测")}
            className="px-2.5 py-1 rounded-md border border-neutral-200 text-[11px] text-neutral-500 hover:text-brand-600"
          >
            重新检测
          </button>
          <button
            onClick={() => run(`/papers/${id}/analyze`, "分析")}
            className="px-2.5 py-1 rounded-md border border-neutral-200 text-[11px] text-neutral-500 hover:text-brand-600"
          >
            重新分析
          </button>
        </div>
      </div>

      <div className="px-6 py-2 bg-neutral-50 border-b border-neutral-100 shrink-0 flex items-center gap-4 text-[11px] text-neutral-400">
        {STEPS.map((s, i) => (
          <span key={s.key} className="flex items-center gap-1">
            <span className={stepDone(i) ? "text-emerald-500" : "text-neutral-300"}>
              {stepDone(i) ? "✓" : "○"}
            </span>
            {s.label}
            {i < STEPS.length - 1 && <span className="text-neutral-200">—</span>}
          </span>
        ))}
      </div>

      <div className="flex-1 flex min-h-0">
        <aside className="w-56 shrink-0 border-r border-neutral-200 bg-white overflow-y-auto">
          <div className="px-4 py-3 text-[11px] font-medium text-neutral-400">论文目录</div>
          <nav className="pb-4">
            {toc.map((item) => (
              <a
                key={item.id + item.text}
                href={`#${item.id}`}
                className={`block px-4 py-1 text-[12px] truncate hover:bg-neutral-50 ${
                  item.level <= 2 ? "text-neutral-700 font-medium" : "text-neutral-400"
                }`}
                style={{ paddingLeft: `${8 + item.level * 8}px` }}
              >
                {item.text}
              </a>
            ))}
            {figures.length > 0 && (
              <div className="mt-3 pt-3 border-t border-neutral-100">
                {figures.map((f) => (
                  <div key={f.id} className="px-4 py-1 text-[11px] text-neutral-400">
                    Figure {f.figure_number}
                  </div>
                ))}
              </div>
            )}
          </nav>
        </aside>

        <section className="flex-1 min-w-0 overflow-y-auto bg-white">
          <article className="max-w-3xl mx-auto px-10 py-8">
            {markdown ? (
              <Markdown content={markdown} paperId={id} />
            ) : (
              <div className="text-neutral-400 text-sm mt-20 text-center">
                {status === "PARSING" || status === "UPLOADED"
                  ? "正在解析论文…"
                  : "暂无可阅读的 Markdown 内容"}
              </div>
            )}
            {paper?.abstract && !markdown && (
              <div className="mt-8 p-4 bg-neutral-50 rounded-lg text-[13px] text-neutral-600">
                {paper.abstract}
              </div>
            )}
          </article>
        </section>

        <aside className="w-[360px] shrink-0 border-l border-neutral-200">
          <ChatPanel paperId={id} paperTitle={paper?.title} />
        </aside>
      </div>
    </div>
  );
}
