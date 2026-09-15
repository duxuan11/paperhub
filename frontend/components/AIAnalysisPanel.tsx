"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { apiGet, apiPost, apiPut } from "@/lib/api";
import type { AIAnalysisPayload, Job } from "@/lib/types";
import {
  initialSelectedSkills,
  orderResults,
  skillLabel,
} from "@/lib/aiAnalysis";
import { Markdown } from "@/components/Markdown";

const POLL_MS = 4000;
const POLL_MAX = 45; // 最多约 3 分钟

/**
 * 论文级 AI 分析面板：选择 Skills / 模型 / 自定义要求，基于 MinerU 结果执行分析，
 * 并按 Skill 分区展示结构化结果。与普通 Chat 不同，这里不进行自由对话。
 */
export function AIAnalysisPanel({ paperId }: { paperId: string }) {
  const [data, setData] = useState<AIAnalysisPayload | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [model, setModel] = useState("");
  const [prompt, setPrompt] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [running, setRunning] = useState(false);
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null);
  const pollRef = useRef<number | null>(null);

  const load = useCallback(
    async (reset: boolean) => {
      try {
        const payload = await apiGet<AIAnalysisPayload>(
          `/papers/${paperId}/ai-analysis`
        );
        setData(payload);
        if (reset) {
          setSelected(initialSelectedSkills(payload.config));
          setModel(payload.config.model || payload.config.default_model || "");
          setPrompt(payload.config.custom_prompt || "");
          setEnabled(payload.config.enabled);
          setDirty(false);
        }
        return payload;
      } catch (e) {
        setNotice({ ok: false, text: `加载失败：${String(e)}` });
        return null;
      }
    },
    [paperId]
  );

  useEffect(() => {
    setData(null);
    setNotice(null);
    load(true);
  }, [load]);

  useEffect(
    () => () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    },
    []
  );

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
    setRunning(false);
  }, []);

  const pollUntilDone = useCallback(() => {
    if (pollRef.current) window.clearInterval(pollRef.current);
    setRunning(true);
    let tries = 0;
    pollRef.current = window.setInterval(async () => {
      tries += 1;
      const jobs = await apiGet<Job[]>(`/papers/${paperId}/jobs`).catch(
        () => [] as Job[]
      );
      const latest = jobs.find((j) => j.job_type === "analyze");
      const done = latest?.status === "SUCCESS" || latest?.status === "FAILED";
      if (done) {
        stopPolling();
        await load(false);
        setNotice(
          latest?.status === "SUCCESS"
            ? { ok: true, text: "分析完成。" }
            : { ok: false, text: `分析失败：${latest?.error || "未知错误"}` }
        );
      } else if (tries >= POLL_MAX) {
        stopPolling();
        await load(false);
        setNotice({ ok: false, text: "分析仍在进行，请稍后刷新查看结果。" });
      }
    }, POLL_MS);
  }, [load, paperId, stopPolling]);

  function toggleSkill(name: string) {
    setDirty(true);
    setSelected((cur) =>
      cur.includes(name) ? cur.filter((n) => n !== name) : [...cur, name]
    );
  }

  function payloadConfig() {
    return {
      enabled,
      model,
      selected_skills: selected,
      custom_prompt: prompt,
    };
  }

  async function save() {
    setBusy(true);
    setNotice(null);
    try {
      await apiPut(`/papers/${paperId}/ai-analysis/config`, payloadConfig());
      await load(true);
      setNotice({ ok: true, text: "配置已保存。" });
    } catch (e) {
      setNotice({ ok: false, text: `保存失败：${String(e)}` });
    } finally {
      setBusy(false);
    }
  }

  async function run() {
    if (selected.length === 0) {
      setNotice({ ok: false, text: "请至少选择一个 Skill。" });
      return;
    }
    setBusy(true);
    setNotice(null);
    try {
      await apiPut(`/papers/${paperId}/ai-analysis/config`, payloadConfig());
      await apiPost(`/papers/${paperId}/ai-analysis/run`, payloadConfig());
      setDirty(false);
      setNotice({ ok: true, text: "已开始 AI 分析，正在读取 MinerU 解析结果…" });
      pollUntilDone();
    } catch (e) {
      setNotice({ ok: false, text: `分析失败：${String(e)}` });
    } finally {
      setBusy(false);
    }
  }

  if (!data) {
    return (
      <div className="text-[13px] text-neutral-400 py-16 text-center">
        正在加载 AI 分析配置…
      </div>
    );
  }

  const available = data.config.available_skills || [];
  const results = orderResults(data.results || [], selected);
  const parsed = data.parsed;

  return (
    <div className="max-w-3xl mx-auto px-8 py-8 space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-neutral-900">AI 分析</h1>
          <p className="mt-1 text-[12px] text-neutral-500">
            配置 PaperHub 如何分析这篇论文（基于 MinerU 解析结果，不重新读取 PDF）
          </p>
        </div>
        <label className="flex items-center gap-2 text-[12px] text-neutral-600 shrink-0">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => {
              setEnabled(e.target.checked);
              setDirty(true);
            }}
          />
          启用 AI 分析
        </label>
      </header>

      {!parsed && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-[12px] text-amber-700">
          MinerU 解析尚未完成，暂时无法进行 AI 分析。请等待解析完成后再试。
        </div>
      )}

      {notice && (
        <div
          className={`rounded-lg px-4 py-2.5 text-[12px] ${
            notice.ok
              ? "bg-emerald-50 text-emerald-700"
              : "bg-red-50 text-red-600"
          }`}
        >
          {notice.text}
        </div>
      )}

      {/* Skills */}
      <section className="rounded-xl border border-neutral-200 bg-white">
        <div className="px-5 py-3 border-b border-neutral-100 flex items-start gap-3">
          <div className="min-w-0">
            <div className="text-[13px] font-semibold text-neutral-800">
              分析 Skills
            </div>
            <div className="text-[11px] text-neutral-400">
              选择用于分析这篇论文的 Skill（内置 + 自定义）
            </div>
          </div>
          <span className="flex-1" />
          <Link
            href="/settings?section=skills"
            className="shrink-0 rounded-md border border-neutral-200 px-2.5 py-1 text-[11px] text-neutral-500 hover:border-brand-300 hover:text-brand-600"
          >
            管理 Skills
          </Link>
        </div>
        <div className="divide-y divide-neutral-50">
          {available.length === 0 && (
            <div className="px-5 py-4 text-[12px] text-neutral-400">
              未发现可用的 Skill。
            </div>
          )}
          {available.map((s) => {
            const checked = selected.includes(s.name);
            return (
              <label
                key={s.name}
                className="flex items-start gap-3 px-5 py-3 cursor-pointer hover:bg-neutral-50"
              >
                <input
                  type="checkbox"
                  className="mt-0.5"
                  checked={checked}
                  onChange={() => toggleSkill(s.name)}
                />
                <span className="min-w-0">
                  <span className="block text-[13px] font-medium text-neutral-800">
                    {s.name}
                  </span>
                  {s.description && (
                    <span className="block text-[11px] text-neutral-400">
                      {s.description}
                    </span>
                  )}
                </span>
              </label>
            );
          })}
        </div>
      </section>

      {/* Model */}
      <section className="rounded-xl border border-neutral-200 bg-white px-5 py-4">
        <div className="text-[13px] font-semibold text-neutral-800">AI 模型</div>
        <div className="text-[11px] text-neutral-400 mb-2">
          留空则使用系统默认（{data.config.default_model || "未配置"}）
        </div>
        <input
          value={model}
          onChange={(e) => {
            setModel(e.target.value);
            setDirty(true);
          }}
          placeholder={data.config.default_model || "deepseek-chat"}
          className="w-full px-3 py-2 rounded-lg border border-neutral-200 text-[13px] focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
        />
      </section>

      {/* Prompt */}
      <section className="rounded-xl border border-neutral-200 bg-white px-5 py-4">
        <div className="text-[13px] font-semibold text-neutral-800">
          分析要求 / Prompt
        </div>
        <div className="text-[11px] text-neutral-400 mb-2">
          可选：作为额外系统要求追加在各 Skill 之后，用于微调口吻、篇幅与关注点
        </div>
        <textarea
          value={prompt}
          onChange={(e) => {
            setPrompt(e.target.value);
            setDirty(true);
          }}
          rows={6}
          placeholder="根据选中的 Skills 分析论文，结论需可追溯到章节 / Figure；论文未提供的信息请标注「论文未提供相关信息」。"
          className="w-full px-3 py-2 rounded-lg border border-neutral-200 text-[13px] leading-relaxed focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
        />
      </section>

      <div className="flex items-center gap-3">
        <button
          onClick={save}
          disabled={busy || !dirty}
          className="px-4 py-2 rounded-lg border border-neutral-200 text-[13px] font-medium text-neutral-600 disabled:opacity-40 hover:border-brand-300 hover:text-brand-600"
        >
          保存配置
        </button>
        <button
          onClick={run}
          disabled={busy || running || !parsed || !enabled}
          className="px-4 py-2 rounded-lg bg-brand-600 text-white text-[13px] font-medium disabled:opacity-40 hover:bg-brand-700"
        >
          {running ? "分析中…" : "开始 AI 分析"}
        </button>
      </div>

      {/* Results */}
      <section className="pt-2">
        <div className="text-[13px] font-semibold text-neutral-800 mb-3">
          分析结果
        </div>
        {results.length === 0 ? (
          <div className="rounded-xl border border-dashed border-neutral-200 px-5 py-10 text-center text-[12px] text-neutral-400">
            尚无分析结果。选择 Skills 后点击「开始 AI 分析」。
          </div>
        ) : (
          <div className="space-y-3">
            {results.map((r) => {
              const { description } = skillLabel(r.skill, available);
              return (
                <details
                  key={r.skill}
                  open
                  className="rounded-xl border border-neutral-200 bg-white overflow-hidden"
                >
                  <summary className="px-5 py-3 cursor-pointer select-none bg-neutral-50">
                    <span className="text-[13px] font-semibold text-neutral-800">
                      {r.skill}
                    </span>
                    {description && (
                      <span className="ml-2 text-[11px] text-neutral-400">
                        {description}
                      </span>
                    )}
                  </summary>
                  <div className="px-5 py-4 border-t border-neutral-100">
                    <Markdown content={r.content} paperId={paperId} />
                  </div>
                </details>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
