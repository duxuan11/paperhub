/**
 * AI 分析纯逻辑（与 UI 解耦，便于 node:test 直接测试）。
 *
 * AI 分析 = 用户选中的 Skills + Model + Custom Prompt，对 MinerU 解析结果
 * 逐 Skill 执行。这里只放与展示/选择相关的纯函数，不发起任何请求。
 */

import type {
  AIAnalysisConfig,
  AIAnalysisResult,
  AnalysisSkill,
} from "./types.ts";

/** 保留选中顺序、去重，并过滤掉当前不存在的 Skill。 */
export function normalizeSelectedSkills(
  selected: string[],
  available: string[]
): string[] {
  const allowed = new Set(available);
  const out: string[] = [];
  for (const raw of selected || []) {
    const name = (raw || "").trim();
    if (name && allowed.has(name) && !out.includes(name)) out.push(name);
  }
  return out;
}

/**
 * 初始选中项：
 * - 已有保存的选择 -> 沿用（并过滤已删除的 Skill）；
 * - 否则全选当前可用 Skills（后端 default_skills 非空时优先）。
 */
export function initialSelectedSkills(config: AIAnalysisConfig): string[] {
  const available = (config.available_skills || []).map((s) => s.name);
  if (config.selected_skills && config.selected_skills.length > 0) {
    return normalizeSelectedSkills(config.selected_skills, available);
  }
  const defaults =
    config.default_skills && config.default_skills.length > 0
      ? config.default_skills
      : available;
  return normalizeSelectedSkills(defaults, available);
}

/**
 * 按选中的 Skill 顺序排列结果；若存在选择之外的旧结果，附在末尾，
 * 保证「按 Skill 分区展示」稳定且不丢数据。
 */
export function orderResults(
  results: AIAnalysisResult[],
  order: string[]
): AIAnalysisResult[] {
  const bySkill = new Map(results.map((r) => [r.skill, r]));
  const out: AIAnalysisResult[] = [];
  const used = new Set<string>();
  for (const skill of order) {
    const row = bySkill.get(skill);
    if (row && !used.has(skill)) {
      out.push(row);
      used.add(skill);
    }
  }
  for (const row of results) {
    if (!used.has(row.skill)) {
      out.push(row);
      used.add(row.skill);
    }
  }
  return out;
}

/** Skill ID -> 展示名（优先用 description 作为副标题）。 */
export function skillLabel(
  name: string,
  available: AnalysisSkill[]
): { title: string; description: string } {
  const found = (available || []).find((s) => s.name === name);
  return {
    title: name,
    description: found?.description || "",
  };
}

/** Skill 名称规则，与后端 skill_registry.NAME_PATTERN 保持一致。 */
export const SKILL_NAME_RE = /^[a-z0-9][a-z0-9-]{0,63}$/;

/** 校验自定义 Skill 名称（小写字母/数字/连字符，字母或数字开头，≤64）。 */
export function isValidSkillName(name: string): boolean {
  return SKILL_NAME_RE.test((name || "").trim());
}

/** 工具列表（逗号 / 空格分隔）<-> 字符串，供编辑器输入。 */
export function toolsToText(tools: string[] | undefined): string {
  return (tools || []).join(", ");
}

export function textToTools(text: string): string[] {
  return (text || "")
    .split(/[,，\s]+/)
    .map((t) => t.trim())
    .filter(Boolean);
}
