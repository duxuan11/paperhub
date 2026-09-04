import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "PaperHub — 科研论文 AI 工作台",
  description: "论文 → AI 分析 → 微信公众号内容生成平台",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className="antialiased">
        <div className="flex h-screen">
          <Sidebar />
          <main className="flex-1 min-w-0 overflow-hidden">{children}</main>
        </div>
      </body>
    </html>
  );
}
