/**
 * 公众号 Theme 渲染器（前端预览用）。
 *
 * 与后端 `publishers/wechat/renderer.py` 保持同一套规则：
 *   - 主题是「CSS 属性 -> 值」的数据对象，渲染逻辑与主题无关；
 *   - 输出全部是 inline style 的 HTML，不依赖任何外部 CSS / class；
 *   - 预览因此与发布到微信的正文高度一致。
 *
 * 新增主题只需后端注册（或新增 JSON），前端无需改代码。
 */

import type { WechatTheme, WechatThemeStyle } from "@/lib/types";

export interface RenderOptions {
  /** {占位名: URL}，替换 ![]({{figure:N}}) 里的占位符 */
  imageMap?: Record<string, string>;
  /** 把相对图片路径（如 images/x.png）解析为可访问 URL */
  resolveSrc?: (src: string) => string;
}

const HEADING_RE = /^(#{1,6})\s+(.*)$/;
const HR_RE = /^(-{3,}|\*{3,}|_{3,})$/;
const UL_RE = /^[-*+]\s+/;
const OL_RE = /^\d+\.\s+/;
const IMG_LINE_RE = /^!\[([^\]]*)\]\(([^)]+)\)\s*$/;
const IMG_INLINE_RE = /!\[([^\]]*)\]\(([^)]+)\)/g;
const LINK_RE = /\[([^\]]+)\]\(([^)]+)\)/g;
const TABLE_SEP_RE = /^\s*\|?[\s:|-]+\|[\s:|-]*$/;
const ITALIC_LINE_RE = /^\*(?!\*)(.+?)\*$/;
const UNDERSCORE_LINE_RE = /^_(.+?)_$/;
const CAPTION_HINT_RE = /^(图|表|Figure|Table|Fig\.?)\s*\d*\s*[:：.．]?/i;

export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

export function escapeAttr(value: string): string {
  return escapeHtml(value).replace(/"/g, "&quot;");
}

/** 把样式对象渲染为 inline style 属性；空样式返回空串。 */
export function styleAttr(style?: WechatThemeStyle): string {
  if (!style) return "";
  const body = Object.entries(style)
    .filter(([, v]) => v)
    .map(([k, v]) => `${k}:${escapeAttr(v)}`)
    .join(";");
  return body ? ` style="${body}"` : "";
}

export function themeCss(theme: WechatTheme, key: string): WechatThemeStyle {
  return theme.styles?.[key] ?? {};
}

function tag(t: string, content: string, style?: WechatThemeStyle): string {
  return `<${t}${styleAttr(style)}>${content}</${t}>`;
}

function inline(text: string, theme: WechatTheme, opts: RenderOptions): string {
  const imageMap = opts.imageMap ?? {};
  const resolve = opts.resolveSrc ?? ((s: string) => s);
  let out = escapeHtml(text);
  out = out.replace(IMG_INLINE_RE, (_m, alt: string, rawSrc: string) => {
    const src = resolve(imageMap[rawSrc] ?? rawSrc);
    return `<img src="${escapeAttr(src)}" alt="${escapeAttr(alt)}"${styleAttr(
      themeCss(theme, "image")
    )}>`;
  });
  out = out.replace(
    LINK_RE,
    (_m, label: string, href: string) =>
      `<a href="${escapeAttr(href)}"${styleAttr(themeCss(theme, "link"))}>${label}</a>`
  );
  out = out.replace(
    /\*\*(.+?)\*\*/g,
    (_m, s: string) => tag("strong", s, themeCss(theme, "strong"))
  );
  out = out.replace(
    /(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g,
    (_m, s: string) => tag("em", s, themeCss(theme, "em"))
  );
  out = out.replace(
    /`(.+?)`/g,
    (_m, s: string) => tag("code", s, themeCss(theme, "code"))
  );
  return out;
}

function looksLikeCaption(line: string): boolean {
  if (!line) return false;
  if (ITALIC_LINE_RE.test(line) || UNDERSCORE_LINE_RE.test(line)) return true;
  return CAPTION_HINT_RE.test(line);
}

function stripCaption(line: string): string {
  const m = ITALIC_LINE_RE.exec(line) ?? UNDERSCORE_LINE_RE.exec(line);
  return m ? m[1] : line;
}

function renderTable(
  lines: string[],
  start: number,
  theme: WechatTheme,
  opts: RenderOptions
): { html: string; next: number } {
  const cells = (row: string) =>
    row
      .trim()
      .replace(/^\||\|$/g, "")
      .split("|")
      .map((c) => c.trim());

  const header = cells(lines[start]);
  let i = start + 2;
  const body: string[][] = [];
  while (i < lines.length && lines[i].includes("|") && lines[i].trim()) {
    body.push(cells(lines[i]));
    i += 1;
  }
  const thStyle = themeCss(theme, "th");
  const tdStyle = themeCss(theme, "td");
  const head = header
    .map((c) => `<th${styleAttr(thStyle)}>${inline(c, theme, opts)}</th>`)
    .join("");
  const rows = body
    .map(
      (row) =>
        `<tr>${row
          .map((c) => `<td${styleAttr(tdStyle)}>${inline(c, theme, opts)}</td>`)
          .join("")}</tr>`
    )
    .join("");
  const html =
    `<table${styleAttr(themeCss(theme, "table"))}><thead><tr>${head}</tr></thead>` +
    `<tbody>${rows}</tbody></table>`;
  return { html, next: i };
}

/** 把 Markdown 渲染为带 inline style 的公众号 HTML。 */
export function renderWechatHtml(
  md: string,
  theme: WechatTheme,
  opts: RenderOptions = {}
): string {
  const imageMap = opts.imageMap ?? {};
  const lines = md.split("\n");
  const blocks: string[] = [];
  let i = 0;
  const total = lines.length;

  while (i < total) {
    const stripped = lines[i].trim();
    if (!stripped) {
      i += 1;
      continue;
    }

    // 代码块
    if (stripped.startsWith("```")) {
      i += 1;
      const code: string[] = [];
      while (i < total && !lines[i].trim().startsWith("```")) {
        code.push(lines[i]);
        i += 1;
      }
      i += 1;
      blocks.push(tag("pre", escapeHtml(code.join("\n")), themeCss(theme, "pre")));
      continue;
    }

    // 标题
    const h = HEADING_RE.exec(stripped);
    if (h) {
      const level = Math.min(h[1].length, 6);
      const key = `h${level}`;
      blocks.push(tag(key, inline(h[2].trim(), theme, opts), themeCss(theme, key)));
      i += 1;
      continue;
    }

    // 分割线
    if (HR_RE.test(stripped)) {
      blocks.push(tag("hr", "", themeCss(theme, "hr")));
      i += 1;
      continue;
    }

    // 引用（合并连续行）
    if (stripped.startsWith(">")) {
      const quote: string[] = [];
      while (i < total && lines[i].trim().startsWith(">")) {
        quote.push(lines[i].trim().replace(/^>/, "").trim());
        i += 1;
      }
      const body = quote
        .filter((q) => q !== "")
        .map((q) => inline(q, theme, opts))
        .join("<br>");
      blocks.push(tag("blockquote", body, themeCss(theme, "blockquote")));
      continue;
    }

    // 列表
    if (UL_RE.test(stripped) || OL_RE.test(stripped)) {
      const ordered = OL_RE.test(stripped);
      const pattern = ordered ? OL_RE : UL_RE;
      const listTag = ordered ? "ol" : "ul";
      const items: string[] = [];
      while (i < total) {
        const s = lines[i].trim();
        const m = pattern.exec(s);
        if (!m) break;
        items.push(inline(s.slice(m[0].length).trim(), theme, opts));
        i += 1;
      }
      const li = items
        .map((it) => `<li${styleAttr(themeCss(theme, "li"))}>${it}</li>`)
        .join("");
      blocks.push(tag(listTag, li, themeCss(theme, listTag)));
      continue;
    }

    // 表格
    if (stripped.includes("|") && i + 1 < total && TABLE_SEP_RE.test(lines[i + 1])) {
      const { html, next } = renderTable(lines, i, theme, opts);
      blocks.push(html);
      i = next;
      continue;
    }

    // 独占一行的图片（支持紧随其后的图片说明）
    const img = IMG_LINE_RE.exec(stripped);
    if (img) {
      const resolve = opts.resolveSrc ?? ((s: string) => s);
      const src = resolve(imageMap[img[2]] ?? img[2]);
      blocks.push(
        tag(
          "p",
          `<img src="${escapeAttr(src)}" alt="${escapeAttr(
            img[1]
          )}"${styleAttr(themeCss(theme, "image"))}>`,
          { margin: "0" }
        )
      );
      i += 1;
      let j = i;
      while (j < total && !lines[j].trim()) j += 1;
      if (j < total && looksLikeCaption(lines[j].trim())) {
        blocks.push(
          tag(
            "p",
            inline(stripCaption(lines[j].trim()), theme, opts),
            themeCss(theme, "caption")
          )
        );
        i = j + 1;
      }
      continue;
    }

    // 普通段落
    blocks.push(tag("p", inline(stripped, theme, opts), themeCss(theme, "paragraph")));
    i += 1;
  }

  let body = blocks.join("\n");
  for (const [placeholder, url] of Object.entries(imageMap)) {
    if (body.includes(placeholder)) body = body.split(placeholder).join(escapeAttr(url));
  }
  return tag("section", body, themeCss(theme, "article"));
}
