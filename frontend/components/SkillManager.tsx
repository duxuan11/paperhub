"use client";

import { useCallback, useEffect, useState } from "react";
import { apiDelete, apiGet, apiPost, apiPut } from "@/lib/api";
import type { AnalysisSkill } from "@/lib/types";
import { isValidSkillName, textToTools, toolsToText } from "@/lib/aiAnalysis";

/** 编辑器草稿。 */
interface Draft {
  isNew: boolean;
  /** 是否是「自定义覆盖内置」的编辑（名称不可改） */
  isCustom: boolean;
  overridesBuiltin: boolean;
  name: string;
  description: string;
  tools: string;
  prompt: string;
}

function emptyDraft(): Draft {
  return {
    isNew: true,
    isCustom: false,
    overridesBuiltin: false,
    name: "",
    description: "",
    tools: "",
    prompt: "",
  };
}

/**
 * 自定义 Skill 管理：查看 / 新建 / 修改 / 删除。
 *
 * - 内置 Skill 只读，但可「覆盖编辑」（创建同名自定义 Skill）与「基于此新建」；
 * - 自定义 Skill 可自由修改与删除；删除覆盖项后内置内容自动恢复；
 * - 所有 Skill 由后端统一加载，AI 分析只保存 Skill ID。
 */
export function SkillManager() {
  const [skills, setSkills] = useState<AnalysisSkill[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiGet<{ skills: AnalysisSkill[] }>("/skills");
      setSkills(data.skills || []);
      setError("");
    } catch (e) {
      setError(`Skill 加载失败：${e}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function startCreate() {
    setNotice("");
    setDraft(emptyDraft());
  }

  function startEdit(skill: AnalysisSkill, override: boolean) {
    setNotice("");
    setDraft({
      isNew: override,
      isCustom: !override,
      overridesBuiltin: override || !!skill.overrides_builtin,
      name: skill.name,
      description: skill.description || "",
      tools: toolsToText(skill.tools),
      prompt: skill.prompt || "",
    });
  }

  async function save() {
    if (!draft) return;
    if (!draft.isCustom && !isValidSkillName(draft.name)) {
      setNotice("Skill 名称只能包含小写字母、数字与连字符，且以字母或数字开头。");
      return;
    }
    setBusy("save");
    setNotice("");
    const body = {
      name: draft.name.trim(),
      description: draft.description.trim(),
      tools: textToTools(draft.tools),
      prompt: draft.prompt,
    };
    try {
      if (draft.isNew) {
        await apiPost("/skills", body);
      } else {
        await apiPut(`/skills/${encodeURIComponent(draft.name)}`, {
          description: body.description,
          tools: body.tools,
          prompt: body.prompt,
        });
      }
      setDraft(null);
      await load();
      setNotice("已保存。");
    } catch (e) {
      setNotice(`保存失败：${e}`);
    } finally {
      setBusy("");
    }
  }

  async function remove(skill: AnalysisSkill) {
    const label = skill.overrides_builtin
      ? `恢复「${skill.name}」的内置内容？`
      : `确定删除自定义 Skill「${skill.name}」？`;
    if (!confirm(label)) return;
    setBusy(`del-${skill.name}`);
    try {
      await apiDelete(`/skills/${encodeURIComponent(skill.name)}`);
      await load();
      setNotice(skill.overrides_builtin ? "已恢复内置内容。" : "已删除。");
    } catch (e) {
      alert(`操作失败：${e}`);
    } finally {
      setBusy("");
    }
  }

  return (
    <div>
      <div className="flex items-start gap-3">
        <div>
          <h2 className="text-[15px] font-semibold text-neutral-900">AI 分析 Skills</h2>
          <p className="text-[12px] text-neutral-500 mt-0.5">
            内置 Skill 只读，可覆盖或复制后修改；自定义 Skill 保存在数据库，同名时覆盖内置。
          </p>
        </div>
        <span className="flex-1" />
        <button
          onClick={startCreate}
          className="rounded-lg bg-brand-600 px-3 py-1.5 text-[12px] text-white hover:bg-brand-700"
        >
          + 新建 Skill
        </button>
      </div>

      {notice && (
        <p className="mt-3 text-[12px] text-emerald-600">{notice}</p>
      )}
      {loading && <p className="mt-6 text-[13px] text-neutral-400">加载中…</p>}
      {error && <p className="mt-6 text-[13px] text-red-500">{error}</p>}

      {draft && (
        <div className="mt-5 rounded-xl border border-brand-200 bg-white p-5">
          <div className="text-[13px] font-semibold text-neutral-800">
            {draft.isNew ? "新建 Skill" : "编辑自定义 Skill"}
          </div>
          <div className="mt-4 grid gap-3">
            <label className="grid gap-1">
              <span className="text-[12px] text-neutral-500">名称（Skill ID）</span>
              <input
                value={draft.name}
                disabled={!draft.isNew}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                placeholder="例如：my-summary"
                className="rounded-md border border-neutral-200 px-2.5 py-1.5 text-[13px] focus:border-brand-300 focus:outline-none disabled:bg-neutral-50"
              />
              {draft.overridesBuiltin && draft.isNew && (
                <span className="text-[11px] text-amber-600">
                  将创建同名自定义 Skill 覆盖内置内容；删除后内置内容自动恢复。
                </span>
              )}
            </label>
            <label className="grid gap-1">
              <span className="text-[12px] text-neutral-500">描述</span>
              <input
                value={draft.description}
                onChange={(e) => setDraft({ ...draft, description: e.target.value })}
                placeholder="用于列表展示，例如：对论文做结构化总结"
                className="rounded-md border border-neutral-200 px-2.5 py-1.5 text-[13px] focus:border-brand-300 focus:outline-none"
              />
            </label>
            <label className="grid gap-1">
              <span className="text-[12px] text-neutral-500">工具 Tools（逗号分隔，可选）</span>
              <input
                value={draft.tools}
                onChange={(e) => setDraft({ ...draft, tools: e.target.value })}
                placeholder="get_paper, get_paper_markdown, get_paper_figures"
                className="rounded-md border border-neutral-200 px-2.5 py-1.5 text-[13px] focus:border-brand-300 focus:outline-none"
              />
            </label>
            <label className="grid gap-1">
              <span className="text-[12px] text-neutral-500">Prompt（Skill 正文）</span>
              <textarea
                value={draft.prompt}
                onChange={(e) => setDraft({ ...draft, prompt: e.target.value })}
                rows={14}
                placeholder="你是一名……请按以下结构分析论文……"
                className="rounded-md border border-neutral-200 px-3 py-2 text-[13px] leading-relaxed focus:border-brand-300 focus:outline-none"
              />
            </label>
          </div>
          <div className="mt-4 flex items-center gap-2">
            <button
              onClick={save}
              disabled={busy === "save"}
              className="rounded-lg bg-brand-600 px-3 py-1.5 text-[12px] text-white hover:bg-brand-700 disabled:opacity-50"
            >
              {busy === "save" ? "保存中…" : "保存"}
            </button>
            <button
              onClick={() => setDraft(null)}
              className="rounded-lg border border-neutral-200 px-3 py-1.5 text-[12px] text-neutral-600"
            >
              取消
            </button>
          </div>
        </div>
      )}

      <div className="mt-5 divide-y divide-neutral-100 rounded-xl border border-neutral-200 bg-white">
        {skills.map((skill) => {
          const custom = skill.source === "custom";
          return (
            <div key={skill.name} className="flex items-center gap-3 px-5 py-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="truncate text-[13px] font-medium text-neutral-800">
                    {skill.name}
                  </span>
                  <span
                    className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium ${
                      custom
                        ? "bg-brand-100 text-brand-700"
                        : "bg-neutral-200 text-neutral-600"
                    }`}
                  >
                    {custom
                      ? skill.overrides_builtin
                        ? "覆盖内置"
                        : "自定义"
                      : "内置"}
                  </span>
                </div>
                <div className="truncate text-[11px] text-neutral-400">
                  {skill.description || "—"}
                  {skill.tools?.length ? ` · tools: ${skill.tools.join(", ")}` : ""}
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-1.5">
                {custom ? (
                  <>
                    <button
                      onClick={() => startEdit(skill, false)}
                      className="rounded-md border border-neutral-200 px-2 py-1 text-[11px] text-neutral-600 hover:border-brand-300"
                    >
                      编辑
                    </button>
                    <button
                      disabled={!!busy}
                      onClick={() => remove(skill)}
                      className="rounded-md px-2 py-1 text-[11px] text-neutral-400 hover:text-red-500 disabled:opacity-50"
                    >
                      {busy === `del-${skill.name}`
                        ? "…"
                        : skill.overrides_builtin
                          ? "恢复内置"
                          : "删除"}
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      onClick={() => startEdit(skill, true)}
                      className="rounded-md border border-neutral-200 px-2 py-1 text-[11px] text-neutral-600 hover:border-brand-300"
                    >
                      覆盖编辑
                    </button>
                    <button
                      onClick={() => {
                        setDraft({
                          ...emptyDraft(),
                          description: skill.description || "",
                          tools: toolsToText(skill.tools),
                          prompt: skill.prompt || "",
                        });
                      }}
                      className="rounded-md border border-neutral-200 px-2 py-1 text-[11px] text-neutral-600 hover:border-brand-300"
                    >
                      基于此新建
                    </button>
                  </>
                )}
              </div>
            </div>
          );
        })}
        {!loading && skills.length === 0 && (
          <div className="px-5 py-6 text-[12px] text-neutral-400">暂无 Skill。</div>
        )}
      </div>
    </div>
  );
}
