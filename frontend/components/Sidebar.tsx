"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

function Icon({ path, className }: { path: string; className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={path} />
    </svg>
  );
}

// 论文库 / 任务 / 微信公众号 / AI 分析 / 设置
const NAV = [
  {
    href: "/",
    label: "论文库",
    icon: "M4 5.5A1.5 1.5 0 0 1 5.5 4H10a2 2 0 0 1 2 2v13a2 2 0 0 0-2-2H4Z M20 5.5A1.5 1.5 0 0 0 18.5 4H14a2 2 0 0 0-2 2v13a2 2 0 0 1 2-2h6Z",
  },
  {
    href: "/tasks",
    label: "任务",
    icon: "M9 6h11 M9 12h11 M9 18h11 M4 6h.01 M4 12h.01 M4 18h.01",
  },
  {
    href: "/articles",
    label: "微信公众号",
    icon: "M22 2 11 13 M22 2l-7 20-4-9-9-4Z",
  },
  {
    href: "/analysis",
    label: "AI 分析",
    icon: "M12 3l1.9 4.6L18.5 9.5l-4.6 1.9L12 16l-1.9-4.6L5.5 9.5l4.6-1.9Z M19 15l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8Z M5 16l.6 1.5L7 18l-1.4.6L5 20l-.6-1.4L3 18l1.4-.5Z",
  },
  {
    href: "/settings",
    label: "设置",
    icon: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.9 1.2 2 2 0 1 1-4 0 1.7 1.7 0 0 0-2.9-1.2l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.7 1.7 0 0 0 3 15a2 2 0 1 1 0-4 1.7 1.7 0 0 0 1.2-2.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1A1.7 1.7 0 0 0 10 3a2 2 0 1 1 4 0 1.7 1.7 0 0 0 2.9 1.2l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1A1.7 1.7 0 0 0 21 11a2 2 0 1 1 0 4Z",
  },
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
              <Icon path={item.icon} className="w-4 h-4 shrink-0" />
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
