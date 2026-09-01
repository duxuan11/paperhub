"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import type { Job } from "@/lib/types";

const JOB_LABELS: Record<string, string> = {
  parse: "MinerU 解析",
  detect_figures: "Figure 检测",
  analyze: "AI 分析",
  generate_wechat: "生成公众号文章",
  publish_wechat: "发布",
};

const JOB_COLORS: Record<string, string> = {
  PENDING: "bg-neutral-100 text-neutral-600",
  RUNNING: "bg-amber-100 text-amber-700",
  SUCCESS: "bg-emerald-100 text-emerald-700",
  FAILED: "bg-rose-100 text-rose-700",
};

export default function TasksPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        setJobs(await apiGet<Job[]>("/jobs?limit=200"));
      } finally {
        setLoading(false);
      }
    };
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto px-8 py-8">
        <h1 className="text-2xl font-bold text-neutral-900">任务</h1>
        <p className="text-[13px] text-neutral-500 mt-1">后台任务执行状态</p>

        <div className="mt-6 space-y-2">
          {loading ? (
            <div className="text-neutral-400 text-sm">加载中…</div>
          ) : jobs.length === 0 ? (
            <div className="text-neutral-400 text-sm">暂无任务</div>
          ) : (
            jobs.map((j) => (
              <div key={j.id} className="rounded-lg border border-neutral-200 bg-white px-4 py-3">
                <div className="flex items-center gap-3">
                  <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium ${JOB_COLORS[j.status] || ""}`}>
                    {j.status}
                  </span>
                  <span className="text-[13px] font-medium text-neutral-800">
                    {JOB_LABELS[j.job_type] || j.job_type}
                  </span>
                  <span className="text-[11px] text-neutral-400">
                    paper={j.paper_id ? j.paper_id.slice(0, 8) : "-"}
                  </span>
                  <span className="flex-1" />
                  {j.status === "RUNNING" && (
                    <div className="w-24 h-1.5 rounded-full bg-neutral-100 overflow-hidden">
                      <div
                        className="h-full bg-brand-500 transition-all"
                        style={{ width: `${j.progress}%` }}
                      />
                    </div>
                  )}
                </div>
                {j.error && <div className="mt-1 text-[12px] text-rose-600">{j.error}</div>}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
