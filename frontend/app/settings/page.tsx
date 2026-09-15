"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPut } from "@/lib/api";
import type { Health } from "@/lib/types";
import { WechatThemeManager } from "@/components/WechatThemeManager";
import { SkillManager } from "@/components/SkillManager";

interface SettingsInfo {
  llm_base_url: string;
  llm_model: string;
  llm_configured: boolean;
  mineru_configured: boolean;
  wechat_configured: boolean;
  yolo_configured: boolean;
  auth_enabled: boolean;
}

interface SkillDetail {
  name: string;
  description: string;
  tools: string[];
  prompt: string;
}

interface AnalysisPrompt {
  skill: string;
  prompt: string;
  default_skill: string;
  default_prompt: string;
  skills: SkillDetail[];
}

type Section = "overview" | "skills" | "wechat";
type WechatTab = "account" | "themes";

export default function SettingsPage() {
  const [health, setHealth] = useState<Health | null>(null);
  const [info, setInfo] = useState<SettingsInfo | null>(null);

  const [cfg, setCfg] = useState<AnalysisPrompt | null>(null);
  const [skill, setSkill] = useState("");
  const [prompt, setPrompt] = useState("");
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null);
  const [dirty, setDirty] = useState(false);

  const [section, setSection] = useState<Section>("overview");
  const [wechatTab, setWechatTab] = useState<WechatTab>("account");

  useEffect(() => {
    apiGet<Health>("/health").then(setHealth).catch(console.error);
    apiGet<SettingsInfo>("/settings").then(setInfo).catch(console.error);
    apiGet<AnalysisPrompt>("/settings/analysis-prompt")
      .then((c) => {
        setCfg(c);
        setSkill(c.skill);
        setPrompt(c.prompt);
      })
      .catch(console.error);
    const wanted = new URLSearchParams(window.location.search).get("section");
    if (wanted === "skills" || wanted === "wechat" || wanted === "overview") {
      setSection(wanted);
    }
  }, []);

  // 载入某个 Skill 的正文到编辑器（覆盖当前内容，便于二次改写）
  function loadSkillPrompt(s: SkillDetail) {
    setSkill(s.name);
    setPrompt(s.prompt);
    setDirty(true);
    setNotice({
      ok: true,
      text: `已把「${s.name}」的提示词载入编辑器，可直接改写后保存（会作为「用户自定义要求」追加在该 Skill 之后）。`,
    });
  }

  async function save(nextSkill = skill, nextPrompt = prompt) {
    setSaving(true);
    setNotice(null);
    try {
      const saved = await apiPut<AnalysisPrompt>("/settings/analysis-prompt", {
        skill: nextSkill,
        prompt: nextPrompt,
      });
      setCfg(saved);
      setSkill(saved.skill);
      setPrompt(saved.prompt);
      setDirty(false);
      setNotice({ ok: true, text: "已保存，后续「AI 分析」将使用这套配置。" });
    } catch (e) {
      setNotice({ ok: false, text: `保存失败：${String(e)}` });
    } finally {
      setSaving(false);
    }
  }

  async function resetPrompt() {
    setPrompt("");
    setDirty(true);
    await save(skill, "");
  }

  const rows: { label: string; ok: boolean; value: string }[] = [
    {
      label: "LLM",
      ok: !!info?.llm_configured,
      value: info ? `${info.llm_base_url} / ${info.llm_model}` : "…",
    },
    {
      label: "MinerU",
      ok: !!info?.mineru_configured,
      value: info?.mineru_configured ? "已配置" : "Mock 模式",
    },
    {
      label: "YOLO",
      ok: !!info?.yolo_configured,
      value: info?.yolo_configured ? "已配置" : "启发式模式",
    },
    {
      label: "微信公众号",
      ok: !!info?.wechat_configured,
      value: info?.wechat_configured ? "已配置" : "Mock 模式",
    },
  ];

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl px-8 py-8">
        <h1 className="text-2xl font-bold text-neutral-900">设置</h1>
        <p className="mt-1 text-[13px] text-neutral-500">
          通过环境变量（.env）配置各服务；留空的 Key 将使用 Mock 实现。
        </p>

        {/* 一级导航 */}
        <div className="mt-6 flex items-center gap-1 border-b border-neutral-200">
          {(
            [
              ["overview", "概览"],
              ["skills", "AI 分析 Skills"],
              ["wechat", "微信公众号"],
            ] as [Section, string][]
          ).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setSection(key)}
              className={`-mb-px border-b-2 px-3 py-2 text-[13px] transition-colors ${
                section === key
                  ? "border-brand-600 font-medium text-brand-700"
                  : "border-transparent text-neutral-500 hover:text-neutral-800"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {section === "overview" && (
          <div className="mt-6">
            <div className="divide-y divide-neutral-100 rounded-xl border border-neutral-200 bg-white">
              {rows.map((r) => (
                <div key={r.label} className="flex items-center px-5 py-4">
                  <span className="w-28 text-[13px] font-medium text-neutral-700">
                    {r.label}
                  </span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                      r.ok
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-amber-100 text-amber-700"
                    }`}
                  >
                    {r.ok ? "真实" : "Mock"}
                  </span>
                  <span className="ml-4 flex-1 truncate text-[12px] text-neutral-500">
                    {r.value}
                  </span>
                </div>
              ))}
            </div>

            <div className="mt-6 rounded-lg bg-neutral-50 p-4 text-[12px] leading-relaxed text-neutral-400">
              <p className="mb-1 font-medium text-neutral-500">配置项（.env）</p>
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
        )}

        {section === "skills" && (
          <div className="mt-6">
            <SkillManager />
          </div>
        )}

        {section === "wechat" && (
          <div className="mt-6">
            <div className="flex items-center gap-1">
              {(
                [
                  ["account", "账号"],
                  ["themes", "文章模板"],
                ] as [WechatTab, string][]
              ).map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => setWechatTab(key)}
                  className={`rounded-lg px-3 py-1.5 text-[12px] transition-colors ${
                    wechatTab === key
                      ? "bg-brand-50 font-medium text-brand-700"
                      : "text-neutral-500 hover:bg-neutral-50"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            {wechatTab === "account" && (
              <div className="mt-4">
                <div className="divide-y divide-neutral-100 rounded-xl border border-neutral-200 bg-white">
                  <div className="flex items-center px-5 py-4">
                    <span className="w-28 text-[13px] font-medium text-neutral-700">
                      公众号凭据
                    </span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                        info?.wechat_configured
                          ? "bg-emerald-100 text-emerald-700"
                          : "bg-amber-100 text-amber-700"
                      }`}
                    >
                      {info?.wechat_configured ? "已配置" : "Mock 模式"}
                    </span>
                    <span className="ml-4 flex-1 text-[12px] text-neutral-500">
                      {info?.wechat_configured
                        ? "草稿会真实推送到公众号草稿箱"
                        : "未配置 WECHAT_APP_ID / WECHAT_APP_SECRET，仅记录本地发布记录"}
                    </span>
                  </div>
                  <div className="flex items-center px-5 py-4">
                    <span className="w-28 text-[13px] font-medium text-neutral-700">
                      运行模式
                    </span>
                    <span className="text-[12px] text-neutral-500">
                      {health?.wechat_mode === "real" ? "real" : "mock"}
                    </span>
                  </div>
                </div>

                <div className="mt-6 rounded-lg bg-neutral-50 p-4 text-[12px] leading-relaxed text-neutral-400">
                  <p className="mb-1 font-medium text-neutral-500">
                    微信公众号相关环境变量
                  </p>
                  <code className="block text-[11px]">
                    WECHAT_APP_ID / WECHAT_APP_SECRET
                    <br />
                    WECHAT_THUMB_MEDIA_ID（可选，草稿封面永久素材）
                  </code>
                </div>
              </div>
            )}

            {wechatTab === "themes" && (
              <div className="mt-4">
                <WechatThemeManager />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
