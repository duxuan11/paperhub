"use client";

import { useEffect, useRef, useState } from "react";
import { streamChat } from "@/lib/api";
import type { ChatMessage } from "@/lib/types";

const SUGGESTIONS = [
  "这篇论文的核心创新是什么？",
  "作者使用了什么实验方法？",
  "分析 Figure 1",
  "这篇论文的方法有什么局限？",
];

export function ChatPanel({
  paperId,
  paperTitle,
}: {
  paperId?: string;
  paperTitle?: string | null;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send(text?: string) {
    const message = (text ?? input).trim();
    if (!message || streaming) return;
    setInput("");
    const history = messages;
    setMessages((m) => [...m, { role: "user", content: message }]);
    setMessages((m) => [...m, { role: "assistant", content: "" }]);
    setStreaming(true);
    try {
      await streamChat(
        {
          message,
          paper_id: paperId || null,
          history: history.map((h) => ({ role: h.role, content: h.content })),
        },
        (delta) => {
          setMessages((m) => {
            const copy = [...m];
            const last = copy[copy.length - 1];
            if (last && last.role === "assistant") {
              last.content += delta;
            }
            return copy;
          });
        }
      );
    } catch (e) {
      setMessages((m) => {
        const copy = [...m];
        const last = copy[copy.length - 1];
        if (last && last.role === "assistant") {
          last.content += `\n\n[错误] ${String(e)}`;
        }
        return copy;
      });
    } finally {
      setStreaming(false);
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 border-b border-neutral-200 bg-white">
        <div className="text-sm font-semibold text-neutral-800">AI 助手</div>
        <div className="text-[11px] text-neutral-400 truncate">
          {paperTitle ? `正在分析：${paperTitle}` : "自由问答"}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 bg-neutral-50">
        {messages.length === 0 && (
          <div className="space-y-2 mt-2">
            <p className="text-[12px] text-neutral-400">试试这样问：</p>
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => send(s)}
                className="block w-full text-left text-[13px] px-3 py-2 rounded-lg border border-neutral-200 bg-white text-neutral-600 hover:border-brand-300 hover:text-brand-600 transition-colors"
              >
                {s}
              </button>
            ))}
          </div>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] px-3 py-2 rounded-xl text-[13px] leading-relaxed whitespace-pre-wrap ${
                m.role === "user"
                  ? "bg-brand-600 text-white"
                  : "bg-white text-neutral-800 border border-neutral-200"
              }`}
            >
              {m.content || (m.role === "assistant" && streaming ? "…" : "")}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="px-3 py-3 bg-white border-t border-neutral-200">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="针对论文提问…"
            className="flex-1 px-3 py-2 rounded-lg border border-neutral-200 text-[13px] focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
          />
          <button
            onClick={() => send()}
            disabled={streaming || !input.trim()}
            className="px-4 py-2 rounded-lg bg-brand-600 text-white text-[13px] font-medium disabled:opacity-40 hover:bg-brand-700 transition-colors"
          >
            发送
          </button>
        </div>
      </div>
    </div>
  );
}
