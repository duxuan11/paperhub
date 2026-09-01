const STATUS_COLORS: Record<string, string> = {
  UPLOADED: "bg-neutral-100 text-neutral-600",
  PARSING: "bg-amber-100 text-amber-700",
  PARSED: "bg-sky-100 text-sky-700",
  FIGURE_DETECTING: "bg-amber-100 text-amber-700",
  READY: "bg-emerald-100 text-emerald-700",
  ANALYZING: "bg-amber-100 text-amber-700",
  ANALYZED: "bg-violet-100 text-violet-700",
  CONTENT_GENERATED: "bg-blue-100 text-blue-700",
  PUBLISHED: "bg-emerald-100 text-emerald-700",
  FAILED: "bg-rose-100 text-rose-700",
};

const STATUS_LABELS: Record<string, string> = {
  UPLOADED: "已上传",
  PARSING: "解析中",
  PARSED: "已解析",
  FIGURE_DETECTING: "检测 Figure",
  READY: "就绪",
  ANALYZING: "AI 分析中",
  ANALYZED: "已分析",
  CONTENT_GENERATED: "已生成内容",
  PUBLISHED: "已发布",
  FAILED: "失败",
};

export function StatusBadge({ status }: { status: string }) {
  const color = STATUS_COLORS[status] || "bg-neutral-100 text-neutral-600";
  const label = STATUS_LABELS[status] || status;
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium ${color}`}>
      {label}
    </span>
  );
}
