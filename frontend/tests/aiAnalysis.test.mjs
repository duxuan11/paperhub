/**
 * AI 分析纯逻辑单元测试（node:test + 类型擦除，无额外依赖）。
 *
 * 运行：npm --prefix frontend test
 */

import test from "node:test";
import assert from "node:assert/strict";

import {
  initialSelectedSkills,
  isValidSkillName,
  normalizeSelectedSkills,
  orderResults,
  skillLabel,
  textToTools,
  toolsToText,
} from "../lib/aiAnalysis.ts";

const SKILLS = [
  { name: "paper-summary", description: "结构化总结", tools: [], prompt: "p" },
  { name: "figure-analysis", description: "逐图分析", tools: [], prompt: "p" },
  { name: "paper-method-analysis", description: "方法分析", tools: [], prompt: "p" },
];

function config(overrides = {}) {
  return {
    paper_id: "p1",
    enabled: true,
    model: "",
    selected_skills: [],
    custom_prompt: "",
    default_model: "deepseek-chat",
    default_skills: [],
    available_skills: SKILLS,
    ...overrides,
  };
}

test("normalizeSelectedSkills keeps order, dedupes, drops unknown", () => {
  const out = normalizeSelectedSkills(
    ["figure-analysis", "paper-summary", "figure-analysis", "gone"],
    SKILLS.map((s) => s.name)
  );
  assert.deepEqual(out, ["figure-analysis", "paper-summary"]);
});

test("initialSelectedSkills prefers saved selection", () => {
  const out = initialSelectedSkills(
    config({ selected_skills: ["paper-method-analysis", "gone"] })
  );
  assert.deepEqual(out, ["paper-method-analysis"]);
});

test("initialSelectedSkills falls back to default skills", () => {
  const out = initialSelectedSkills(
    config({ default_skills: ["paper-summary"] })
  );
  assert.deepEqual(out, ["paper-summary"]);
});

test("initialSelectedSkills selects all available when nothing configured", () => {
  const out = initialSelectedSkills(config());
  assert.deepEqual(out, [
    "paper-summary",
    "figure-analysis",
    "paper-method-analysis",
  ]);
});

test("orderResults follows selection order and keeps extras", () => {
  const results = [
    { skill: "legacy-skill", content: "C", paper_id: "p1", model: null, created_at: null, updated_at: null },
    { skill: "figure-analysis", content: "B", paper_id: "p1", model: null, created_at: null, updated_at: null },
    { skill: "paper-summary", content: "A", paper_id: "p1", model: null, created_at: null, updated_at: null },
  ];
  const ordered = orderResults(results, ["paper-summary", "figure-analysis"]);
  assert.deepEqual(
    ordered.map((r) => r.skill),
    ["paper-summary", "figure-analysis", "legacy-skill"]
  );
});

test("skillLabel resolves description with fallback", () => {
  assert.equal(skillLabel("paper-summary", SKILLS).description, "结构化总结");
  assert.equal(skillLabel("unknown", SKILLS).description, "");
});

test("isValidSkillName mirrors the backend rule", () => {
  for (const ok of ["my-skill", "skill2", "a", "a-b-c-1"]) {
    assert.equal(isValidSkillName(ok), true, ok);
  }
  for (const bad of [
    "",
    "A",
    "my skill",
    "../etc",
    "-lead",
    "中文",
    "a/b",
    "a".repeat(65),
  ]) {
    assert.equal(isValidSkillName(bad), false, bad);
  }
});

test("tools text round-trips", () => {
  assert.equal(toolsToText(["get_paper", "get_figure"]), "get_paper, get_figure");
  assert.deepEqual(textToTools("get_paper, get_figure"), ["get_paper", "get_figure"]);
  assert.deepEqual(textToTools("a，b  c"), ["a", "b", "c"]);
  assert.deepEqual(textToTools(""), []);
});
