"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
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

      <div className="flex-1 flex min-h-0">
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

        <section className="flex-1 min-w-0 flex flex-col border-r border-neutral-200 bg-white">
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

        <aside className="w-[420px] shrink-0 overflow-y-auto bg-neutral-50">
          <div className="px-4 py-3 text-[11px] font-medium text-neutral-400 border-b border-neutral-100 bg-white">
            微信公众号预览
          </div>
          <div className="px-6 py-6 bg-white min-h-full">
            <Markdown content={preview} paperId={article?.paper_id || undefined} />
          </div>
        </aside>
      </div>
    </div>
  );
}
