/**
 * 微信公众号 Theme 的「设计变量 -> 组件样式」编译器（前端镜像）。
 *
 * 与后端 `publishers/wechat/theme_config.py` 保持同一套规则与取值，用于模板
 * 编辑器的**实时预览**；保存/发布链路始终使用后端的编译结果，保证所见即所得。
 *
 * 只输出微信可内联的普通 CSS 属性：不使用 CSS 变量 / 伪元素 / 外部样式表。
 */

import type {
  WechatThemeConfig,
  WechatThemeStyle,
} from "@/lib/types";

export const FONT_STACK =
  "-apple-system,BlinkMacSystemFont,'PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif";
export const MONO_STACK = "Menlo,Consolas,'Courier New',monospace";

export const DEFAULT_THEME_CONFIG: WechatThemeConfig = {
  colors: {
    primary: "#2563EB",
    secondary: "#64748B",
    text: "#1E293B",
    muted: "#64748B",
    background: "#FFFFFF",
    border: "#E2E8F0",
  },
  typography: {
    fontFamily: FONT_STACK,
    bodySize: "15px",
    bodyLineHeight: "1.8",
    heading1Size: "24px",
    heading2Size: "19px",
    heading3Size: "17px",
    captionSize: "13px",
  },
  components: {},
};

/** 把用户 config 深合并到默认配置，返回完整配置（新对象）。 */
export function mergeThemeConfig(
  config?: Partial<WechatThemeConfig> | null
): WechatThemeConfig {
  const cfg: WechatThemeConfig = {
    colors: { ...DEFAULT_THEME_CONFIG.colors },
    typography: { ...DEFAULT_THEME_CONFIG.typography },
    components: {},
  };
  if (!config) return cfg;
  for (const key of Object.keys(cfg.colors) as (keyof typeof cfg.colors)[]) {
    const value = config.colors?.[key];
    if (value) cfg.colors[key] = value;
  }
  for (const key of Object.keys(
    cfg.typography
  ) as (keyof typeof cfg.typography)[]) {
    const value = config.typography?.[key];
    if (value !== undefined && value !== null && value !== "") {
      cfg.typography[key] = value as never;
    }
  }
  for (const [key, overrides] of Object.entries(config.components ?? {})) {
    if (overrides && typeof overrides === "object") {
      cfg.components[key] = { ...overrides };
    }
  }
  return cfg;
}

function parseHex(color: string): [number, number, number] | null {
  if (typeof color !== "string") return null;
  let value = color.trim().replace(/^#/, "");
  if (value.length === 3) {
    value = value
      .split("")
      .map((ch) => ch + ch)
      .join("");
  }
  if (value.length !== 6 || !/^[0-9a-fA-F]{6}$/.test(value)) return null;
  return [
    parseInt(value.slice(0, 2), 16),
    parseInt(value.slice(2, 4), 16),
    parseInt(value.slice(4, 6), 16),
  ];
}

/** Python round() 的「四舍六入五成双」语义，保证与后端逐字节一致。 */
function pyRound(value: number): number {
  const floor = Math.floor(value);
  const diff = value - floor;
  if (diff > 0.5) return floor + 1;
  if (diff < 0.5) return floor;
  return floor % 2 === 0 ? floor : floor + 1;
}

function toHex(value: number): string {
  return value.toString(16).padStart(2, "0");
}

/** 把颜色按 ratio 混向白色（0=原色，1=纯白）。 */
export function tint(color: string, ratio: number): string {
  const rgb = parseHex(color);
  if (!rgb) return color;
  const [r, g, b] = rgb;
  const clamped = Math.max(0, Math.min(1, ratio));
  const mix = (ch: number) => pyRound(ch + (255 - ch) * clamped);
  return `#${toHex(mix(r))}${toHex(mix(g))}${toHex(mix(b))}`;
}

/** 把设计变量编译为渲染器使用的元素样式表。 */
export function compileThemeConfig(
  config?: Partial<WechatThemeConfig> | null
): Record<string, WechatThemeStyle> {
  const cfg = mergeThemeConfig(config);
  const c = cfg.colors;
  const t = cfg.typography;
  const primary = c.primary;
  const text = c.text;
  const bodySize = t.bodySize;
  const lineHeight = t.bodyLineHeight;

  const styles: Record<string, WechatThemeStyle> = {
    article: {
      "font-family": t.fontFamily || FONT_STACK,
      "font-size": bodySize,
      "line-height": lineHeight,
      color: text,
      "background-color": c.background,
      "letter-spacing": "0.2px",
      "word-break": "break-word",
    },
    h1: {
      "font-size": t.heading1Size,
      "font-weight": "700",
      color: text,
      "line-height": "1.4",
      margin: "28px 0 14px",
    },
    h2: {
      "font-size": t.heading2Size,
      "font-weight": "700",
      color: text,
      "line-height": "1.5",
      margin: "26px 0 12px",
      "padding-left": "10px",
      "border-left": `4px solid ${primary}`,
    },
    h3: {
      "font-size": t.heading3Size,
      "font-weight": "600",
      color: text,
      "line-height": "1.5",
      margin: "20px 0 8px",
    },
    h4: {
      "font-size": bodySize,
      "font-weight": "600",
      color: text,
      "line-height": "1.5",
      margin: "18px 0 8px",
    },
    h5: {
      "font-size": "14px",
      "font-weight": "600",
      color: text,
      margin: "16px 0 6px",
    },
    h6: {
      "font-size": "13px",
      "font-weight": "600",
      color: c.muted,
      margin: "14px 0 6px",
    },
    paragraph: {
      "font-size": bodySize,
      "line-height": lineHeight,
      color: text,
      margin: "0 0 16px",
    },
    blockquote: {
      margin: "0 0 16px",
      padding: "12px 16px",
      "background-color": tint(primary, 0.94),
      "border-left": `3px solid ${tint(primary, 0.55)}`,
      color: c.secondary,
      "font-size": bodySize,
      "line-height": "1.7",
      "border-radius": "0 6px 6px 0",
    },
    callout: {
      margin: "0 0 16px",
      padding: "12px 16px",
      "background-color": tint(primary, 0.92),
      "border-left": `3px solid ${primary}`,
      "border-radius": "0 6px 6px 0",
    },
    calloutTitle: {
      "font-size": bodySize,
      "font-weight": "600",
      color: primary,
      margin: "0 0 6px",
    },
    calloutText: {
      "font-size": bodySize,
      "line-height": lineHeight,
      color: text,
      margin: "0",
    },
    image: {
      display: "block",
      width: "100%",
      "max-width": "100%",
      height: "auto",
      margin: "18px auto 6px",
      "border-radius": "8px",
    },
    caption: {
      "font-size": t.captionSize,
      color: c.muted,
      "text-align": "center",
      "line-height": "1.6",
      margin: "0 0 18px",
    },
    ul: { margin: "0 0 16px", "padding-left": "22px" },
    ol: { margin: "0 0 16px", "padding-left": "22px" },
    li: {
      "font-size": bodySize,
      "line-height": lineHeight,
      color: text,
      margin: "0 0 6px",
    },
    hr: {
      border: "none",
      "border-top": `1px solid ${c.border}`,
      margin: "24px 0",
    },
    link: {
      color: primary,
      "text-decoration": "none",
      "border-bottom": `1px solid ${tint(primary, 0.7)}`,
    },
    strong: { "font-weight": "600", color: text },
    em: { "font-style": "italic", color: c.secondary },
    code: {
      "background-color": tint(primary, 0.92),
      color: primary,
      padding: "2px 5px",
      "border-radius": "4px",
      "font-size": "14px",
      "font-family": MONO_STACK,
    },
    pre: {
      "background-color": text,
      color: "#F8FAFC",
      padding: "14px 16px",
      "border-radius": "8px",
      "font-size": "13px",
      "line-height": "1.6",
      "overflow-x": "auto",
      margin: "0 0 16px",
    },
    table: {
      width: "100%",
      "border-collapse": "collapse",
      margin: "0 0 16px",
      "font-size": "14px",
    },
    th: {
      border: `1px solid ${c.border}`,
      "background-color": tint(primary, 0.94),
      padding: "8px 10px",
      "text-align": "left",
      "font-weight": "600",
      color: text,
    },
    td: {
      border: `1px solid ${c.border}`,
      padding: "8px 10px",
      "text-align": "left",
      color: text,
    },
  };

  for (const [key, overrides] of Object.entries(cfg.components)) {
    if (!styles[key]) continue;
    const clean: WechatThemeStyle = {};
    for (const [prop, value] of Object.entries(overrides)) {
      if (value) clean[prop] = String(value);
    }
    styles[key] = { ...styles[key], ...clean };
  }
  return styles;
}

/** 组件编辑器的友好分组（key 与 compileThemeConfig 输出的元素 key 对应）。 */
export const COMPONENT_GROUPS: {
  label: string;
  hint: string;
  fields: { key: string; prop: string; label: string; type: "color" | "text" }[];
}[] = [
  {
    label: "引用块",
    hint: "Markdown > 引用",
    fields: [
      { key: "blockquote", prop: "background-color", label: "背景色", type: "color" },
      { key: "blockquote", prop: "border-left", label: "左侧竖线", type: "text" },
    ],
  },
  {
    label: "图片",
    hint: "Markdown 图片",
    fields: [
      { key: "image", prop: "border-radius", label: "圆角", type: "text" },
      { key: "image", prop: "margin", label: "外边距", type: "text" },
    ],
  },
  {
    label: "图注",
    hint: "图片下方说明文字",
    fields: [
      { key: "caption", prop: "text-align", label: "对齐", type: "text" },
      { key: "caption", prop: "color", label: "颜色", type: "color" },
    ],
  },
  {
    label: "行内代码",
    hint: "`code`",
    fields: [
      { key: "code", prop: "color", label: "文字色", type: "color" },
      { key: "code", prop: "background-color", label: "背景色", type: "color" },
    ],
  },
  {
    label: "代码块",
    hint: "``` 围栏代码",
    fields: [
      { key: "pre", prop: "background-color", label: "背景色", type: "color" },
      { key: "pre", prop: "color", label: "文字色", type: "color" },
    ],
  },
  {
    label: "表格",
    hint: "Markdown 管道表格",
    fields: [
      { key: "th", prop: "background-color", label: "表头背景", type: "color" },
      { key: "td", prop: "border", label: "单元格边框", type: "text" },
    ],
  },
  {
    label: "Callout",
    hint: "> [!NOTE] 提示块",
    fields: [
      { key: "callout", prop: "background-color", label: "背景色", type: "color" },
      { key: "callout", prop: "border-left", label: "左侧竖线", type: "text" },
      { key: "calloutTitle", prop: "color", label: "标题色", type: "color" },
    ],
  },
  {
    label: "分割线",
    hint: "---",
    fields: [
      { key: "hr", prop: "border-top", label: "线条", type: "text" },
    ],
  },
];
