"use client";

import { ChatPanel } from "@/components/ChatPanel";

export default function ChatPage() {
  return (
    <div className="h-full flex flex-col">
      <div className="px-6 py-3 bg-white border-b border-neutral-200 shrink-0">
        <h1 className="text-[15px] font-semibold text-neutral-900">AI Chat</h1>
        <p className="text-[12px] text-neutral-400">自由对话；可选择论文进行针对性问答</p>
      </div>
      <div className="flex-1 min-h-0">
        <ChatPanel />
      </div>
    </div>
  );
}
