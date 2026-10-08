/**
 * 文章图片操作纯逻辑（node:test 可测，不依赖 React / DOM）。
 *
 * 占位符约定：正文 `![...]({{figure:N}})` 按下标引用 `Article.images[N]`。
 * - 排序 = 换图不换位：只重排数组，不改正文（修正 YOLO 顺序）。
 * - 删除 = 下标前移：删掉 `images[index]`，并把正文里 `> index` 的下标 -1，
 *   `=== index` 的引用删除，避免悬空。
 */

const IMAGE_LINE_RE = /^!\[([^\]]*)\]\(\{\{figure:(\d+)\}\}\)$/;
const FIGURE_TOKEN_RE = /\{\{figure:(\d+)\}\}/g;

/** 换图不换位：把 from 位置的图移到 to，返回新数组（不改入参）。 */
export function moveImage(images: string[], from: number, to: number): string[] {
  if (from === to || from < 0 || from >= images.length) return [...images];
  const next = [...images];
  const [item] = next.splice(from, 1);
  next.splice(Math.max(0, Math.min(to, next.length)), 0, item);
  return next;
}

/** 删除 images[index]，并把正文里受影响的 {{figure:N}} 重编号 / 删除。 */
export function removeImage(
  content: string,
  images: string[],
  index: number
): { content: string; images: string[] } {
  if (index < 0 || index >= images.length) {
    return { content, images: [...images] };
  }
  const nextImages = images.filter((_, i) => i !== index);
  // 只删除「独占一行的 `{{figure:index}}` 图片引用」所在的整行；
  // 不在正文其它位置做任何空行规整（代码块内空行必须逐字节保留）。
  const lines = content.split("\n");
  const kept: string[] = [];
  let skipNextBlank = false;
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    if (skipNextBlank) {
      skipNextBlank = false;
      if (line === "") continue; // 与被删行配对的空行，局部队消一个
    }
    const m = IMAGE_LINE_RE.exec(line.trim());
    if (m && Number(m[2]) === index) {
      const prevKept = kept.length > 0 ? kept[kept.length - 1] : undefined;
      if (prevKept === "" && lines[i + 1] === "") {
        skipNextBlank = true; // 前后都是空行时，只删掉其中一个
      }
      continue;
    }
    kept.push(line);
  }
  const nextContent = kept.join("\n").replace(FIGURE_TOKEN_RE, (token, n: string) => {
    const i = Number(n);
    if (i === index) return "";
    if (i > index) return `{{figure:${i - 1}}}`;
    return token;
  });
  return { content: nextContent, images: nextImages };
}

/** 追加一张图，返回新数组与它的下标。 */
export function appendImage(
  images: string[],
  key: string
): { images: string[]; index: number } {
  const next = [...images, key];
  return { images: next, index: next.length - 1 };
}

/** 在光标 / 选区处插入独立一行的图片引用，返回新正文与新光标位。 */
export function insertImageAtCursor(
  content: string,
  selectionStart: number,
  selectionEnd: number,
  index: number,
  alt: string
): { content: string; cursor: number } {
  const start = Math.max(0, Math.min(selectionStart, content.length));
  const end = Math.max(start, Math.min(selectionEnd, content.length));
  const before = content.slice(0, start);
  const after = content.slice(end);
  const image = `![${alt}]({{figure:${index}}})`;
  const lead = before === "" || before.endsWith("\n") ? "" : "\n";
  const inserted = `${lead}${image}\n`;
  return {
    content: `${before}${inserted}${after}`,
    cursor: (before + inserted).length,
  };
}
