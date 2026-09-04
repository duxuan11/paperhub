"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "论文库" },
  { href: "/tasks", label: "任务" },
  { href: "/articles", label: "微信公众号" },
  { href: "/chat", label: "AI Chat" },
  { href: "/settings", label: "设置" },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-56 shrink-0 border-r border-neutral-200 bg-white flex flex-col">
      <div className="px-5 py-5 border-b border-neutral-100">
        <div className="text-lg font-bold text-neutral-900 tracking-tight">PaperHub</div>
        <div className="text-[11px] text-neutral-400 mt-0.5">科研论文 AI 工作台</div>
      </div>
      <nav className="flex-1 px-2 py-3 space-y-0.5">
        {NAV.map((item) => {
          const active =
            item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-[14px] transition-colors ${
                active
                  ? "bg-brand-50 text-brand-700 font-medium"
                  : "text-neutral-600 hover:bg-neutral-50"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="px-5 py-4 border-t border-neutral-100 text-[11px] text-neutral-400">
        PaperHub MVP
      </div>
    </aside>
  );
}
