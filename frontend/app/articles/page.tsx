"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import type { Article } from "@/lib/types";

const STATUS_LABELS: Record<string, string> = {
  DRAFT: "草稿",
  GENERATED: "已生成",
  SENT_TO_PLATFORM: "已发送草稿箱",
  PUBLISHED: "已发布",
};

export default function ArticlesPage() {
  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        setArticles(await apiGet<Article[]>("/articles?limit=200"));
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto px-8 py-8">
        <h1 className="text-2xl font-bold text-neutral-900">微信公众号文章</h1>
        <p className="text-[13px] text-neutral-500 mt-1">AI 生成的文章，可编辑后发送到公众号草稿箱</p>

        <div className="mt-6 space-y-3">
          {loading ? (
            <div className="text-neutral-400 text-sm">加载中…</div>
          ) : articles.length === 0 ? (
            <div className="border-2 border-dashed border-neutral-200 rounded-2xl p-12 text-center text-neutral-400 text-sm">
              暂无文章。请在论文库中对论文点击「生成公众号」。
            </div>
          ) : (
            articles.map((a) => (
              <div key={a.id} className="rounded-xl border border-neutral-200 bg-white p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <Link
                      href={`/articles/${a.id}/edit`}
                      className="text-[15px] font-semibold text-neutral-900 hover:text-brand-600"
                    >
                      {a.title || "未命名"}
                    </Link>
                    <div className="text-[12px] text-neutral-400 mt-1">
                      {a.style ? `${a.style} · ` : ""}
                      {STATUS_LABELS[a.status] || a.status}
                      {a.paper_id ? ` · 论文 ${a.paper_id.slice(0, 8)}` : ""}
                    </div>
                  </div>
                  <Link
                    href={`/articles/${a.id}/edit`}
                    className="px-3 py-1.5 rounded-lg bg-neutral-900 text-white text-[12px] hover:bg-neutral-700 shrink-0"
                  >
                    编辑
                  </Link>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
