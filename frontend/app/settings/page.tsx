"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import type { Health } from "@/lib/types";

interface SettingsInfo {
  llm_base_url: string;
  llm_model: string;
  llm_configured: boolean;
  mineru_configured: boolean;
  wechat_configured: boolean;
  yolo_configured: boolean;
  auth_enabled: boolean;
}

export default function SettingsPage() {
  const [health, setHealth] = useState<Health | null>(null);
  const [info, setInfo] = useState<SettingsInfo | null>(null);

  useEffect(() => {
    apiGet<Health>("/health").then(setHealth).catch(console.error);
    apiGet<SettingsInfo>("/settings").then(setInfo).catch(console.error);
  }, []);

  const rows: { label: string; ok: boolean; value: string }[] = [
    {
      label: "LLM",
      ok: !!info?.llm_configured,
      value: info ? `${info.llm_base_url} / ${info.llm_model}` : "…",
    },
    { label: "MinerU", ok: !!info?.mineru_configured, value: info?.mineru_configured ? "已配置" : "Mock 模式" },
    { label: "YOLO", ok: !!info?.yolo_configured, value: info?.yolo_configured ? "已配置" : "启发式模式" },
    { label: "微信公众号", ok: !!info?.wechat_configured, value: info?.wechat_configured ? "已配置" : "Mock 模式" },
  ];

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-2xl mx-auto px-8 py-8">
        <h1 className="text-2xl font-bold text-neutral-900">设置</h1>
        <p className="text-[13px] text-neutral-500 mt-1">
          通过环境变量（.env）配置各服务；留空的 Key 将使用 Mock 实现。
        </p>

        <div className="mt-6 rounded-xl border border-neutral-200 bg-white divide-y divide-neutral-100">
          {rows.map((r) => (
            <div key={r.label} className="flex items-center px-5 py-4">
              <span className="w-28 text-[13px] font-medium text-neutral-700">{r.label}</span>
              <span
                className={`px-2 py-0.5 rounded-full text-[11px] font-medium ${
                  r.ok ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"
                }`}
              >
                {r.ok ? "真实" : "Mock"}
              </span>
              <span className="flex-1 ml-4 text-[12px] text-neutral-500 truncate">{r.value}</span>
            </div>
          ))}
        </div>

        <div className="mt-6 text-[12px] text-neutral-400 leading-relaxed bg-neutral-50 rounded-lg p-4">
          <p className="font-medium text-neutral-500 mb-1">配置项（.env）</p>
          <code className="block text-[11px]">
            OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL
            <br />
            MINERU_API_URL / MINERU_API_KEY
            <br />
            YOLO_MODEL_PATH / YOLO_ENABLED
            <br />
            WECHAT_APP_ID / WECHAT_APP_SECRET
            <br />
            PAPERHUB_API_KEY
          </code>
        </div>
      </div>
    </div>
  );
}
