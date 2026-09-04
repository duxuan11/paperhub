"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiGet, apiPost, apiUploadFiles } from "@/lib/api";
import type { Paper } from "@/lib/types";
import { StatusBadge } from "@/components/StatusBadge";

export default function DashboardPage() {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  const load = useCallback(async () => {
    try {
      const data = await apiGet<Paper[]>("/papers?limit=100");
      setPapers(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [load]);

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    setUploading(true);
    try {
      await apiUploadFiles(Array.from(files));
      await load();
    } catch (e) {
      alert(`上传失败: ${e}`);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function action(path: string, label: string) {
    try {
      await apiPost(path);
      await load();
    } catch (e) {
      alert(`${label}失败: ${e}`);
    }
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-5xl mx-auto px-8 py-8">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-neutral-900">你的科研论文 AI 工作台</h1>
            <p className="text-[13px] text-neutral-500 mt-1">
              上传 PDF，自动解析、检测 Figure，并用 AI 分析、生成公众号文章
            </p>
          </div>
          <button
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
            className="px-4 py-2.5 rounded-lg bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 disabled:opacity-50 transition-colors"
          >
            {uploading ? "上传中…" : "上传论文"}
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="application/pdf"
            multiple
            hidden
            onChange={(e) => handleFiles(e.target.files)}
          />
        </div>

        <div className="mt-8">
          <h2 className="text-[13px] font-medium text-neutral-500 mb-3">最近论文</h2>
          {loading ? (
            <div className="text-neutral-400 text-sm">加载中…</div>
          ) : papers.length === 0 ? (
            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                handleFiles(e.dataTransfer.files);
              }}
              className="border-2 border-dashed border-neutral-200 rounded-2xl p-16 text-center text-neutral-400"
            >
              <p className="text-sm">拖拽 PDF 到这里，或点击右上角「上传论文」</p>
              <p className="text-xs mt-1">支持一次上传多篇 PDF</p>
            </div>
          ) : (
            <div className="grid gap-3">
              {papers.map((p) => (
                <div
                  key={p.id}
                  className="rounded-xl border border-neutral-200 bg-white p-4 hover:shadow-sm transition-shadow"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <Link
                          href={`/papers/${p.id}`}
                          className="text-[15px] font-semibold text-neutral-900 hover:text-brand-600 truncate"
                        >
                          {p.title || p.filename || "未命名"}
                        </Link>
                        <StatusBadge status={p.status} />
                      </div>
                      <div className="text-[12px] text-neutral-400 mt-1">
                        {(p.journal ? `${p.journal} · ` : "")}
                        {p.year || "—"}
                        {p.filename ? ` · ${p.filename}` : ""}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <Link
                        href={`/papers/${p.id}`}
                        className="px-3 py-1.5 rounded-lg border border-neutral-200 text-[12px] text-neutral-600 hover:border-brand-300 hover:text-brand-600"
                      >
                        阅读
                      </Link>
                      <button
                        onClick={() => action(`/papers/${p.id}/analyze`, "分析")}
                        className="px-3 py-1.5 rounded-lg border border-neutral-200 text-[12px] text-neutral-600 hover:border-brand-300 hover:text-brand-600"
                      >
                        AI 分析
                      </button>
                      <button
                        onClick={() => {
                          action(`/papers/${p.id}/generate-wechat`, "生成").then(() =>
                            router.push("/articles")
                          );
                        }}
                        className="px-3 py-1.5 rounded-lg bg-neutral-900 text-white text-[12px] hover:bg-neutral-700"
                      >
                        生成公众号
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
