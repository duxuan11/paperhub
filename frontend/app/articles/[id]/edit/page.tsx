"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { apiGet, apiPatch, apiPost, fileUrl } from "@/lib/api";
import type { Article, PublishRecord } from "@/lib/types";
import { Markdown } from "@/components/Markdown";

const REC_STATUS: Record<string, string> = {
  PENDING: "推送中",
  SUCCESS: "成功",
  FAILED: "失败",
};

/* ——— 可拖动分栏尺寸约束（px） ——— */
/** 右侧公众号预览最小宽度：低于此值手机阅读区会被压扁 */
const PREVIEW_MIN = 340;
/** 右侧公众号预览最大宽度：避免预览把编辑区吃光 */
const PREVIEW_MAX = 900;
/** 左侧 Markdown 编辑区最小宽度，由拖动/窗口变化时自动保证 */
const EDITOR_MIN = 380;
/** 分隔条占位宽度（w-2） */
const DIVIDER_WIDTH = 8;
/** 默认预览宽度 */
const PREVIEW_DEFAULT = 440;

function extractOutline(md: string) {
  const items: { level: number; text: string }[] = [];
  for (const line of md.split("\n")) {
    const m = line.match(/^(#{1,4})\s+(.+)$/);
    if (m) items.push({ level: m[1].length, text: m[2].replace(/[*_`]/g, "").trim() });
  }
  return items;
}

function resolveFigures(md: string, images: string[] | null): string {
  if (!images) return md;
  return md.replace(/\{\{figure:(\d+)\}\}/g, (_, n) => {
    const idx = Number(n);
    const key = images[idx];
    return key ? fileUrl(key) : "#";
  });
}

export default function ArticleEditorPage() {
  const { id } = useParams<{ id: string }>();
  const [article, setArticle] = useState<Article | null>(null);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [saving, setSaving] = useState(false);
  const [acting, setActing] = useState("");
  const [notice, setNotice] = useState("");
  // 最近一次公众号推送记录：微信侧失败必须让用户看得见，而不是只弹一句"已发送"
  const [lastRecord, setLastRecord] = useState<PublishRecord | null>(null);
  const [mockMode, setMockMode] = useState(false);

  // ——— 可拖动分栏：编辑区 / 公众号预览 ———
  /** 包住「编辑区 + 分隔条 + 预览」的容器，作为可用宽度的测量基准 */
  const splitRef = useRef<HTMLDivElement | null>(null);
  const dragRef = useRef<{ startX: number; startWidth: number } | null>(null);
  const [previewWidth, setPreviewWidth] = useState(PREVIEW_DEFAULT);
  const [resizing, setResizing] = useState(false);

  const load = useCallback(async () => {
    const a = await apiGet<Article>(`/articles/${id}`);
    setArticle(a);
    setTitle(a.title || "");
    setContent(a.content || "");
  }, [id]);

  const loadRecords = useCallback(async () => {
    try {
      const recs = await apiGet<PublishRecord[]>(
        `/wechat/records?article_id=${id}&limit=1`
      );
      setLastRecord(recs[0] || null);
    } catch {
      // 记录接口不可用时不影响编辑
    }
  }, [id]);

  useEffect(() => {
    load();
    loadRecords();
  }, [load, loadRecords]);

  /**
   * 把预览宽度收敛到合法区间：
   * 下限 PREVIEW_MIN 保证手机阅读区可用，上限 = 容器宽度 - 编辑区最小宽度 - 分隔条，
   * 因此拖动永远不会把编辑区挤没，也不会让整行溢出容器。
   */
  const clampPreviewWidth = useCallback((width: number) => {
    const available = splitRef.current?.clientWidth ?? 0;
    const max = Math.max(
      PREVIEW_MIN,
      Math.min(PREVIEW_MAX, available - EDITOR_MIN - DIVIDER_WIDTH)
    );
    return Math.round(Math.min(Math.max(width, PREVIEW_MIN), max));
  }, []);

  function startResize(e: React.PointerEvent<HTMLDivElement>) {
    if (e.button !== 0) return;
    e.preventDefault();
    dragRef.current = { startX: e.clientX, startWidth: previewWidth };
    setResizing(true);
  }

  // 拖动期间监听 window：鼠标移出分隔条甚至移出窗口也能继续跟随
  useEffect(() => {
    if (!resizing) return;
    const onMove = (e: PointerEvent) => {
      const drag = dragRef.current;
      if (!drag) return;
      // 向左拖动 => 右侧预览变宽
      setPreviewWidth(clampPreviewWidth(drag.startWidth + (drag.startX - e.clientX)));
    };
    const onEnd = () => {
      dragRef.current = null;
      setResizing(false);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onEnd);
    window.addEventListener("pointercancel", onEnd);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onEnd);
      window.removeEventListener("pointercancel", onEnd);
    };
  }, [resizing, clampPreviewWidth]);

  // 拖动时全局禁用文本选中 + 锁定 col-resize 光标，避免选中文字、光标闪烁和布局跳动
  useEffect(() => {
    if (!resizing) return;
    document.body.classList.add("is-resizing");
    return () => document.body.classList.remove("is-resizing");
  }, [resizing]);

  // 窗口或容器尺寸变化时重新收敛宽度，保证任何时候布局都合法（不横向溢出）
  useEffect(() => {
    const onResize = () => setPreviewWidth((w) => clampPreviewWidth(w));
    window.addEventListener("resize", onResize);
    const el = splitRef.current;
    const observer =
      typeof ResizeObserver !== "undefined" ? new ResizeObserver(onResize) : null;
    if (el && observer) observer.observe(el);
    onResize();
    return () => {
      window.removeEventListener("resize", onResize);
      observer?.disconnect();
    };
  }, [clampPreviewWidth]);

  const outline = useMemo(() => extractOutline(content), [content]);
  const preview = useMemo(
    () => resolveFigures(content, article?.images || null),
    [content, article]
  );

  function flash(msg: string) {
    setNotice(msg);
    setTimeout(() => setNotice(""), 2500);
  }

  async function save() {
    setSaving(true);
    try {
      await apiPatch(`/articles/${id}`, { title, content });
      flash("已保存草稿");
    } catch (e) {
      alert(`保存失败: ${e}`);
    } finally {
      setSaving(false);
    }
  }

  async function runAction(action: string, label: string) {
    setActing(label);
    try {
      const updated = await apiPost<Article>(`/articles/${id}/action`, { action });
      setArticle(updated);
      setTitle(updated.title || "");
      setContent(updated.content || "");
      flash(`${label}完成`);
    } catch (e) {
      alert(`${label}失败: ${e}`);
    } finally {
      setActing("");
    }
  }

  /** 轮询发布记录，把微信侧的真实结果反馈给用户。 */
  async function trackPublishResult(
    recordId: string,
    prevId: string | null,
    publish: boolean
  ) {
    const action = publish ? "发布" : "发送草稿箱";
    for (let i = 0; i < 40; i++) {
      await new Promise((r) => setTimeout(r, 1500));
      let recs: PublishRecord[] = [];
      try {
        recs = await apiGet<PublishRecord[]>(`/wechat/records?article_id=${id}&limit=5`);
      } catch {
        continue;
      }
      const rec =
        recs.find((r) => r.id === recordId) ??
        recs.find((r) => r.id !== prevId) ??
        null;
      if (!rec) continue;
      setLastRecord(rec);
      if (rec.status === "PENDING") continue;
      if (rec.status === "SUCCESS") {
        flash(publish ? "已发布到公众号" : "已发送到公众号草稿箱");
      } else {
        setNotice("");
        alert(`${action}失败：\n${rec.error || "未知错误"}`);
      }
      return;
    }
    flash("任务仍在执行，请到「任务」页查看进度");
  }

  async function sendDraft(publish: boolean) {
    const label = publish ? "发布" : "发送草稿箱";
    setActing(publish ? "发布中" : "发送中");
    try {
      const prevId = lastRecord?.id ?? null;
      const res = await apiPost<{ record_id: string; mock: boolean }>(
        publish ? "/wechat/publish" : "/wechat/draft",
        { article_id: id, publish }
      );
      setMockMode(!!res.mock);
      flash(
        res.mock
          ? "已入队：当前为 Mock 模式（未配置公众号凭据），不会真的发送"
          : `${label}任务已提交，等待微信返回…`
      );
      // 不阻塞界面：后台轮询真实结果（成功/失败原因都会展示）
      void trackPublishResult(res.record_id, prevId, publish);
    } catch (e) {
      alert(`${label}失败: ${e}`);
    } finally {
      setActing("");
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 px-6 py-3 bg-white border-b border-neutral-200 shrink-0">
        <Link href="/articles" className="text-neutral-400 hover:text-neutral-600 text-[13px]">
          ← 返回
        </Link>
        <span className="text-[15px] font-semibold text-neutral-900">文章编辑器</span>
        {notice && <span className="text-[12px] text-emerald-600">{notice}</span>}
        {mockMode && (
          <span className="text-[12px] text-amber-600">Mock 模式（未配置公众号凭据）</span>
        )}
        <span className="flex-1" />
        <button
          onClick={() => runAction("polish", "润色")}
          disabled={!!acting}
          className="px-3 py-1.5 rounded-lg border border-neutral-200 text-[12px] text-neutral-600 hover:border-brand-300"
        >
          {acting === "润色" ? "…" : "AI 润色"}
        </button>
        <button
          onClick={() => runAction("shorten", "缩短")}
          disabled={!!acting}
          className="px-3 py-1.5 rounded-lg border border-neutral-200 text-[12px] text-neutral-600 hover:border-brand-300"
        >
          {acting === "缩短" ? "…" : "AI 缩短"}
        </button>
        <button
          onClick={() => runAction("expand", "扩展")}
          disabled={!!acting}
          className="px-3 py-1.5 rounded-lg border border-neutral-200 text-[12px] text-neutral-600 hover:border-brand-300"
        >
          {acting === "扩展" ? "…" : "AI 扩展"}
        </button>
        <button
          onClick={() => runAction("regenerate", "重新生成")}
          disabled={!!acting}
          className="px-3 py-1.5 rounded-lg border border-neutral-200 text-[12px] text-neutral-600 hover:border-brand-300"
        >
          {acting === "重新生成" ? "…" : "重新生成"}
        </button>
        <button
          onClick={save}
          disabled={saving}
          className="px-3 py-1.5 rounded-lg border border-brand-200 text-brand-600 text-[12px]"
        >
          {saving ? "保存中…" : "保存草稿"}
        </button>
        <button
          onClick={() => sendDraft(false)}
          disabled={!!acting}
          className="px-3 py-1.5 rounded-lg bg-brand-600 text-white text-[12px] hover:bg-brand-700"
        >
          {acting === "发送中" ? "…" : "发送到草稿箱"}
        </button>
        <button
          onClick={() => sendDraft(true)}
          disabled={!!acting}
          className="px-3 py-1.5 rounded-lg bg-neutral-900 text-white text-[12px] hover:bg-neutral-700"
        >
          {acting === "发布中" ? "…" : "发布"}
        </button>
      </div>

      {(lastRecord || mockMode) && (
        <div className="px-6 py-2 bg-neutral-50 border-b border-neutral-200 text-[12px] flex items-center gap-2 shrink-0">
          {lastRecord && (
            <>
              <span className="text-neutral-400">上次推送</span>
              <span
                className={
                  lastRecord.status === "FAILED"
                    ? "text-red-600"
                    : lastRecord.status === "SUCCESS"
                    ? "text-emerald-600"
                    : "text-neutral-500"
                }
              >
                {REC_STATUS[lastRecord.status] || lastRecord.status}
              </span>
              {lastRecord.external_id && (
                <span className="text-neutral-400">id={lastRecord.external_id}</span>
              )}
              {lastRecord.error && (
                <span className="text-red-500 truncate max-w-[60vw]" title={lastRecord.error}>
                  {lastRecord.error}
                </span>
              )}
            </>
          )}
        </div>
      )}

      <div className="flex-1 flex min-h-0 overflow-hidden">
        {/* 文章结构栏：固定宽度，不参与拖动 */}
        <aside className="w-52 shrink-0 border-r border-neutral-200 bg-white overflow-y-auto">
          <div className="px-4 py-3 text-[11px] font-medium text-neutral-400">文章结构</div>
          <nav className="pb-4">
            {outline.map((o, i) => (
              <div
                key={i}
                className="px-4 py-1 text-[12px] truncate text-neutral-500"
                style={{ paddingLeft: `${8 + o.level * 8}px` }}
              >
                {o.text}
              </div>
            ))}
          </nav>
        </aside>

        {/* 编辑区 + 可拖动分隔条 + 公众号预览；作为可拖动宽度的测量基准 */}
        <div ref={splitRef} className="flex-1 min-w-0 flex overflow-hidden">
          <section className="flex-1 min-w-0 flex flex-col bg-white">
            <div className="px-4 py-2 border-b border-neutral-100">
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="标题"
                className="w-full text-[15px] font-semibold px-2 py-1.5 rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500/20"
              />
            </div>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              className="flex-1 resize-none px-6 py-4 font-mono text-[13px] leading-relaxed focus:outline-none"
              placeholder="Markdown 正文…"
            />
          </section>

          {/* 竖向分隔条：hover / 拖动有明显视觉反馈，双击恢复默认宽度 */}
          <div
            role="separator"
            aria-orientation="vertical"
            aria-label="拖动调整公众号预览宽度"
            aria-valuenow={Math.round(previewWidth)}
            title="拖动调整预览宽度（双击恢复默认）"
            onPointerDown={startResize}
            onDoubleClick={() => setPreviewWidth(clampPreviewWidth(PREVIEW_DEFAULT))}
            className={`group relative w-2 shrink-0 touch-none select-none cursor-col-resize transition-colors ${
              resizing
                ? "bg-brand-100"
                : "bg-neutral-100 hover:bg-brand-50"
            }`}
          >
            <span
              className={`pointer-events-none absolute inset-y-0 left-1/2 -translate-x-1/2 transition-all ${
                resizing
                  ? "w-0.5 bg-brand-500"
                  : "w-px bg-neutral-300 group-hover:w-0.5 group-hover:bg-brand-400"
              }`}
            />
          </div>

          {/* 公众号预览：外层宽度可拖动，内层固定为手机阅读宽度 */}
          <aside
            className="shrink-0 min-w-0 flex flex-col bg-neutral-100"
            style={{ width: previewWidth, minWidth: PREVIEW_MIN }}
          >
            <div className="px-4 py-3 border-b border-neutral-200 bg-white flex items-center gap-2 shrink-0">
              <span className="text-[11px] font-medium text-neutral-400">微信公众号预览</span>
              <span className="text-[11px] text-neutral-300 tabular-nums">
                {previewWidth}px
              </span>
            </div>
            <div className="flex-1 min-h-0 overflow-hidden p-4">
              {/* 手机外壳：固定最大宽度模拟手机阅读区，右栏收窄时自动等比收窄 */}
              <div className="mx-auto flex h-full w-full max-w-[375px] flex-col overflow-hidden rounded-[20px] border border-neutral-200 bg-white shadow-sm">
                <div className="shrink-0 h-8 px-4 flex items-center justify-between border-b border-neutral-100 bg-neutral-50 text-[10px] text-neutral-400 select-none">
                  <span>9:41</span>
                  <span className="tracking-[0.2em]">··· ▮</span>
                </div>
                <div className="shrink-0 px-4 py-3 border-b border-neutral-100">
                  <div className="truncate text-[13px] font-medium text-neutral-800">
                    PaperHub · 科研速递
                  </div>
                  <div className="mt-0.5 truncate text-[11px] text-neutral-400">
                    {title || "未命名文章"}
                  </div>
                </div>
                {/* 正文超出时在手机屏幕内滚动 */}
                <div className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden">
                  <div className="px-4 py-4">
                    <Markdown content={preview} paperId={article?.paper_id || undefined} />
                  </div>
                </div>
              </div>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
