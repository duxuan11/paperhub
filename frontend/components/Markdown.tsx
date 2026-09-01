"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import { fileUrl } from "@/lib/api";

function resolveSrc(src: string | undefined, paperId?: string): string {
  if (!src) return "";
  if (src.startsWith("http://") || src.startsWith("https://") || src.startsWith("/")) {
    return src;
  }
  if (paperId && src.startsWith("images/")) {
    return fileUrl(`${paperId}/${src}`);
  }
  return paperId ? fileUrl(`${paperId}/${src}`) : src;
}

export function Markdown({ content, paperId }: { content: string; paperId?: string }) {
  return (
    <div className="prose-md">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          img: ({ src, alt }) => (
            <img src={resolveSrc(src, paperId)} alt={alt || ""} loading="lazy" />
          ),
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noreferrer">
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
