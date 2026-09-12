"use client";

import { useMemo } from "react";
import { fileUrl } from "@/lib/api";
import type { WechatTheme } from "@/lib/types";
import { renderWechatHtml } from "@/lib/wechatTheme";
import { Markdown } from "@/components/Markdown";

/**
 * 公众号正文预览：使用与发布同源的主题配置，实时渲染成 inline style HTML。
 *
 * - 主题未加载完成时退回普通 Markdown 预览（不阻塞编辑）；
 * - 预览与微信最终正文使用同一套 Theme 数据，因此所见接近所得。
 */
export function WeChatPreview({
  content,
  theme,
  paperId,
}: {
  content: string;
  theme: WechatTheme | null;
  paperId?: string;
}) {
  const html = useMemo(() => {
    if (!theme) return "";
    return renderWechatHtml(content, theme, {
      resolveSrc: (src) => {
        if (!src) return src;
        if (/^(https?:)?\/\//.test(src) || src.startsWith("/") || src.startsWith("data:")) {
          return src;
        }
        return paperId ? fileUrl(`${paperId}/${src}`) : src;
      },
    });
  }, [content, theme, paperId]);

  if (!theme) {
    return <Markdown content={content} paperId={paperId} />;
  }
  return <div dangerouslySetInnerHTML={{ __html: html }} />;
}
