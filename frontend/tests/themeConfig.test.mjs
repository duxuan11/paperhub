/**
 * 前端主题编译器单元测试（node:test + 类型擦除，无额外依赖）。
 *
 * 运行：npm --prefix frontend test
 * 重点验证 compileThemeConfig 与后端 publishers/wechat/theme_config.py
 * 采用同一套设计变量 -> 组件样式规则。
 */

import test from "node:test";
import assert from "node:assert/strict";

import {
  DEFAULT_THEME_CONFIG,
  compileThemeConfig,
  mergeThemeConfig,
  tint,
} from "../lib/themeConfig.ts";
import { renderWechatHtml } from "../lib/wechatTheme.ts";

const RENDERER_KEYS = [
  "article",
  "h1",
  "h2",
  "h3",
  "paragraph",
  "blockquote",
  "callout",
  "calloutTitle",
  "image",
  "caption",
  "code",
  "pre",
  "table",
  "th",
  "td",
  "hr",
  "link",
];

test("tint mixes toward white and tolerates bad input", () => {
  assert.equal(tint("#000000", 1), "#ffffff");
  assert.equal(tint("#000000", 0), "#000000");
  assert.equal(tint("#2563EB", 0.5), "#92b1f5");
  assert.equal(tint("nothex", 0.5), "nothex");
});

test("compileThemeConfig emits every renderer component", () => {
  const styles = compileThemeConfig(DEFAULT_THEME_CONFIG);
  for (const key of RENDERER_KEYS) {
    assert.ok(styles[key], `缺少 ${key}`);
    assert.ok(Object.keys(styles[key]).length > 0, `${key} 为空`);
  }
});

test("colors and typography flow into component styles", () => {
  const styles = compileThemeConfig({
    colors: { primary: "#123456", text: "#222222" },
    typography: { bodySize: "18px", bodyLineHeight: "2", heading1Size: "30px" },
  });
  assert.equal(styles.paragraph["font-size"], "18px");
  assert.equal(styles.paragraph["line-height"], "2");
  assert.equal(styles.paragraph.color, "#222222");
  assert.equal(styles.h1["font-size"], "30px");
  assert.equal(styles.h2["border-left"], "4px solid #123456");
  assert.equal(styles.article["font-size"], "18px");
});

test("compileThemeConfig renders h2 as a tinted section card", () => {
  const styles = compileThemeConfig({ colors: { primary: "#123456" } });
  assert.equal(styles.h2["border-left"], "4px solid #123456");
  assert.equal(styles.h2["background-color"], tint("#123456", 0.93));
  assert.ok(styles.h2["border-radius"]);
});

test("compileThemeConfig centers a short hr rule", () => {
  const styles = compileThemeConfig();
  assert.ok(styles.hr.width);
  assert.ok(String(styles.hr.margin).endsWith("auto"));
});

test("compileThemeConfig gives the table header a primary header", () => {
  const styles = compileThemeConfig({ colors: { primary: "#123456" } });
  assert.equal(styles.th["background-color"], "#123456");
  assert.equal(styles.th.color, "#FFFFFF");
});

test("component overrides win over compiled defaults", () => {
  const styles = compileThemeConfig({
    components: {
      paragraph: { margin: "0 0 30px", color: "#abcdef" },
      h2: { "border-left": "none" },
    },
  });
  assert.equal(styles.paragraph.margin, "0 0 30px");
  assert.equal(styles.paragraph.color, "#abcdef");
  assert.equal(styles.h2["border-left"], "none");
  // 未被覆盖的字段仍保留默认
  assert.ok(styles.paragraph["font-size"]);
});

test("mergeThemeConfig fills missing design variables", () => {
  const cfg = mergeThemeConfig({ colors: { primary: "#FF0000" } });
  assert.equal(cfg.colors.primary, "#FF0000");
  assert.equal(cfg.colors.text, DEFAULT_THEME_CONFIG.colors.text);
  assert.equal(cfg.typography.bodySize, DEFAULT_THEME_CONFIG.typography.bodySize);
  assert.deepEqual(cfg.components, {});
});

const SAMPLE_MD = [
  "# 标题",
  "",
  "正文段落，含 **加粗** 与 `行内代码`。",
  "",
  "> 普通引用",
  "",
  "> [!NOTE]",
  "> Callout 提示",
  "",
  "- 列表项",
  "",
  "| 指标 | 值 |",
  "| --- | --- |",
  "| 准确率 | 91% |",
  "",
  "```python",
  "print(1)",
  "```",
  "",
  "![Figure 1](https://example.com/a.png)",
  "",
  "*图 1：说明文字*",
  "",
  "---",
].join("\n");

test("renderWechatHtml renders every component with inline styles", () => {
  const styles = compileThemeConfig(DEFAULT_THEME_CONFIG);
  const html = renderWechatHtml(SAMPLE_MD, { id: "t", name: "t", styles });

  assert.ok(html.includes("<h1") && html.includes("标题"));
  assert.ok(html.includes("<p") && html.includes("正文段落"));
  assert.ok(html.includes("<blockquote") && html.includes("普通引用"));
  assert.ok(html.includes("<section") && html.includes("Callout 提示"));
  assert.ok(html.includes("<img") && html.includes("图 1：说明文字"));
  assert.ok(html.includes("<table") && html.includes("91%"));
  assert.ok(html.includes("<pre") && html.includes("<code"));
  assert.ok(html.includes("<hr"));
  assert.ok(html.includes('style="'));

  // 微信兼容：不使用外部样式表 / class / 脚本 / CSS 变量
  assert.ok(!html.includes("<style"));
  assert.ok(!html.includes("<link"));
  assert.ok(!html.includes("class="));
  assert.ok(!html.includes("<script"));
  assert.ok(!html.includes("var(--"));
});

test("same article + different theme = same content, different style", () => {
  const a = renderWechatHtml(SAMPLE_MD, {
    id: "a",
    name: "a",
    styles: compileThemeConfig({ colors: { primary: "#FF0000" } }),
  });
  const b = renderWechatHtml(SAMPLE_MD, {
    id: "b",
    name: "b",
    styles: compileThemeConfig({ colors: { primary: "#00AA00" } }),
  });
  assert.notEqual(a, b);
  for (const marker of ["标题", "正文段落", "Callout 提示", "91%", "图 1：说明文字"]) {
    assert.ok(a.includes(marker) && b.includes(marker));
  }
  assert.ok(a.includes("#FF0000"));
  assert.ok(b.includes("#00AA00"));
});
