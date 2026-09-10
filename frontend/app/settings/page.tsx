"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPut } from "@/lib/api";
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

export default function SettingsPage() {
  const [health, setHealth] = useState<Health | null>(null);
  const [info, setInfo] = useState<SettingsInfo | null>(null);

  const [cfg, setCfg] = useState<AnalysisPrompt | null>(null);
  const [skill, setSkill] = useState("");
  const [prompt, setPrompt] = useState("");
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null);
  const [dirty, setDirty] = useState(false);

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
    { label: "MinerU", ok: !!info?.mineru_configured, value: info?.mineru_configured ? "已配置" : "Mock 模式" },
    { label: "YOLO", ok: !!info?.yolo_configured, value: info?.yolo_configured ? "已配置" : "启发式模式" },
    { label: "微信公众号", ok: !!info?.wechat_configured, value: info?.wechat_configured ? "已配置" : "Mock 模式" },
  ];

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-3xl mx-auto px-8 py-8">
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

        {/* ---- AI 分析提示词编辑器 ---- */}
        <div className="mt-8">
          <div className="flex items-baseline gap-3">
            <h2 className="text-lg font-bold text-neutral-900">AI 分析提示词</h2>
            {cfg && (
              <span className="text-[11px] text-neutral-400">
                当前生效 Skill：{cfg.skill}
              </span>
            )}
          </div>
          <p className="text-[12px] text-neutral-500 mt-1 leading-relaxed">
            论文列表里的「分析」按钮会按这里的配置生成分析。分析内容 = Skill（结构框架）+
            自定义要求（下面的编辑器）。留空则只使用 Skill 与内置默认要求。
          </p>

          {/* Skill 入口 */}
          <div className="mt-4">
            <p className="text-[12px] font-medium text-neutral-700 mb-2">
              调用 Skill（点击卡片载入其提示词到编辑器；「设为默认」决定分析用哪个框架）
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {(cfg?.skills || []).map((s) => {
                const active = skill === s.name;
                return (
                  <div
                    key={s.name}
                    className={`rounded-xl border p-3 bg-white transition ${
                      active ? "border-emerald-300 ring-1 ring-emerald-100" : "border-neutral-200"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[13px] font-semibold text-neutral-800 truncate">
                        {s.name}
                      </span>
                      {active && (
                        <span className="shrink-0 px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 text-[10px] font-medium">
                          默认
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-[11px] text-neutral-500 leading-relaxed line-clamp-2">
                      {s.description || "（无描述）"}
                    </p>
                    {s.tools?.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {s.tools.slice(0, 4).map((t) => (
                          <span
                            key={t}
                            className="px-1.5 py-0.5 rounded bg-neutral-100 text-neutral-500 text-[10px] font-mono"
                          >
                            {t}
                          </span>
                        ))}
                      </div>
                    )}
                    <div className="mt-3 flex gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          setSkill(s.name);
                          setDirty(true);
                          setNotice(null);
                        }}
                        className={`px-2.5 py-1 rounded-md text-[11px] font-medium border transition ${
                          active
                            ? "border-emerald-300 bg-emerald-50 text-emerald-700"
                            : "border-neutral-200 text-neutral-600 hover:bg-neutral-50"
                        }`}
                      >
                        {active ? "已设为默认" : "设为默认"}
                      </button>
                      <button
                        type="button"
                        onClick={() => loadSkillPrompt(s)}
                        className="px-2.5 py-1 rounded-md text-[11px] font-medium border border-neutral-200 text-neutral-600 hover:bg-neutral-50 transition"
                      >
                        载入提示词
                      </button>
                    </div>
                  </div>
                );
              })}
              {!cfg && <p className="text-[12px] text-neutral-400">加载中…</p>}
            </div>
          </div>

          {/* 提示词编辑 */}
          <div className="mt-5">
            <div className="flex items-center justify-between mb-2">
              <p className="text-[12px] font-medium text-neutral-700">自定义提示词</p>
              <span className="text-[11px] text-neutral-400">{prompt.length} 字符</span>
            </div>
            <textarea
              value={prompt}
              onChange={(e) => {
                setPrompt(e.target.value);
                setDirty(true);
              }}
              rows={12}
              spellCheck={false}
              placeholder={cfg?.default_prompt || "例如：只用中文，先给结论再给论据……"}
              className="w-full rounded-xl border border-neutral-200 bg-white p-3 text-[12px] leading-relaxed font-mono text-neutral-800 outline-none focus:border-neutral-400 resize-y"
            />
            <div className="mt-1 flex items-center justify-between">
              <p className="text-[11px] text-neutral-400">
                这里的内容以「用户自定义要求」注入，优先级高于通用规则。
              </p>
              <button
                type="button"
                onClick={() => {
                  setPrompt(cfg?.default_prompt || "");
                  setDirty(true);
                }}
                className="text-[11px] text-neutral-500 hover:text-neutral-800 underline underline-offset-2"
              >
                填入内置默认要求
              </button>
            </div>

            <div className="mt-4 flex items-center gap-3">
              <button
                type="button"
                disabled={saving || !dirty}
                onClick={() => save()}
                className="px-4 py-2 rounded-lg bg-neutral-900 text-white text-[12px] font-medium disabled:opacity-40 hover:bg-neutral-800 transition"
              >
                {saving ? "保存中…" : "保存"}
              </button>
              <button
                type="button"
                disabled={saving}
                onClick={resetPrompt}
                className="px-3 py-2 rounded-lg border border-neutral-200 text-[12px] text-neutral-600 hover:bg-neutral-50 disabled:opacity-40 transition"
              >
                清空自定义提示词
              </button>
              {notice && (
                <span
                  className={`text-[12px] ${
                    notice.ok ? "text-emerald-600" : "text-red-600"
                  }`}
                >
                  {notice.text}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* ---- 预览：实际发给模型的分析要求 ---- */}
        {cfg && (
          <details className="mt-6 rounded-xl border border-neutral-200 bg-white">
            <summary className="px-5 py-3 text-[12px] font-medium text-neutral-700 cursor-pointer select-none">
              预览：本次「AI 分析」实际使用的 Skill 框架与自定义要求
            </summary>
            <div className="px-5 pb-4 space-y-3">
              <div>
                <p className="text-[11px] font-medium text-neutral-500 mb-1">
                  Skill：{skill}
                </p>
                <pre className="max-h-56 overflow-auto rounded-lg bg-neutral-50 p-3 text-[11px] leading-relaxed text-neutral-600 whitespace-pre-wrap">
                  {(cfg.skills.find((s) => s.name === skill)?.prompt || "（未找到该 Skill）").slice(0, 4000)}
                </pre>
              </div>
              <div>
                <p className="text-[11px] font-medium text-neutral-500 mb-1">自定义要求</p>
                <pre className="max-h-40 overflow-auto rounded-lg bg-neutral-50 p-3 text-[11px] leading-relaxed text-neutral-600 whitespace-pre-wrap">
                  {prompt.trim() || "（空 —— 将只使用上方 Skill 与内置默认要求）"}
                </pre>
              </div>
            </div>
          </details>
        )}

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
