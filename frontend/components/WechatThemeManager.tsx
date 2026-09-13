"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiDelete, apiGet, apiPost } from "@/lib/api";
import type { WechatTheme } from "@/lib/types";
import { ThemePhonePreview } from "@/components/ThemePhonePreview";

/**
 * 微信公众号推文模板管理：查看 / 复制 / 设为默认 / 删除 / 进入编辑器。
 *
 * 内置模板（is_builtin）只读：可预览、复制、设为默认，但不能编辑或删除。
 */
export function WechatThemeManager() {
  const router = useRouter();
  const [themes, setThemes] = useState<WechatTheme[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setThemes(await apiGet<WechatTheme[]>("/wechat/themes"));
      setError("");
    } catch (e) {
      setError(`主题加载失败：${e}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function run(label: string, fn: () => Promise<unknown>) {
    setBusy(label);
    try {
      await fn();
      await load();
    } catch (e) {
      alert(`操作失败：${e}`);
    } finally {
      setBusy("");
    }
  }

  async function removeTheme(theme: WechatTheme) {
    if (!confirm(`确定删除模板「${theme.name}」？该操作不可撤销。`)) return;
    await run(`delete-${theme.id}`, () => apiDelete(`/wechat/themes/${theme.id}`));
  }

  return (
    <div>
      <div className="flex items-center gap-3">
        <div>
          <h2 className="text-[15px] font-semibold text-neutral-900">推文模板</h2>
          <p className="text-[12px] text-neutral-500 mt-0.5">
            模板只控制排版与配色，文章内容保持 Markdown 不变；发布时自动转为微信公众号
            inline style。
          </p>
        </div>
        <span className="flex-1" />
        <button
          onClick={() => router.push("/settings/wechat-themes/new")}
          className="px-3 py-1.5 rounded-lg bg-brand-600 text-white text-[12px] hover:bg-brand-700"
        >
          + 新建模板
        </button>
      </div>

      {loading && <p className="mt-6 text-[13px] text-neutral-400">加载中…</p>}
      {error && <p className="mt-6 text-[13px] text-red-500">{error}</p>}

      <div className="mt-5 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {themes.map((theme) => {
          const isBuiltin = !!theme.is_builtin;
          return (
            <div
              key={theme.id}
              className="flex flex-col overflow-hidden rounded-xl border border-neutral-200 bg-white"
            >
              <div className="border-b border-neutral-100 px-4 py-3">
                <div className="flex items-center gap-2">
                  <span className="truncate text-[14px] font-semibold text-neutral-900">
                    {theme.name}
                  </span>
                  <span
                    className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium ${
                      isBuiltin
                        ? "bg-neutral-200 text-neutral-600"
                        : "bg-brand-100 text-brand-700"
                    }`}
                  >
                    {isBuiltin ? "Built-in" : "Custom"}
                  </span>
                  {theme.is_default && (
                    <span className="shrink-0 rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700">
                      ✓ Default
                    </span>
                  )}
                </div>
                <p className="mt-1 h-8 overflow-hidden text-[11px] leading-4 text-neutral-400">
                  {theme.description || "—"}
                </p>
              </div>

              <div className="flex-1 bg-neutral-100 p-3">
                <ThemePhonePreview
                  config={theme.config}
                  width={230}
                  bodyHeight={210}
                  compact
                />
              </div>

              <div className="flex flex-wrap items-center gap-1.5 border-t border-neutral-100 px-3 py-2">
                <button
                  onClick={() => router.push(`/settings/wechat-themes/${theme.id}`)}
                  className="rounded-md border border-neutral-200 px-2 py-1 text-[11px] text-neutral-600 hover:border-brand-300"
                >
                  {isBuiltin ? "查看" : "编辑"}
                </button>
                <button
                  disabled={!!busy}
                  onClick={() =>
                    run(`dup-${theme.id}`, () =>
                      apiPost(`/wechat/themes/${theme.id}/duplicate`)
                    )
                  }
                  className="rounded-md border border-neutral-200 px-2 py-1 text-[11px] text-neutral-600 hover:border-brand-300 disabled:opacity-50"
                >
                  {busy === `dup-${theme.id}` ? "…" : "复制"}
                </button>
                {!theme.is_default && (
                  <button
                    disabled={!!busy}
                    onClick={() =>
                      run(`def-${theme.id}`, () =>
                        apiPost(`/wechat/themes/${theme.id}/set-default`)
                      )
                    }
                    className="rounded-md border border-neutral-200 px-2 py-1 text-[11px] text-neutral-600 hover:border-brand-300 disabled:opacity-50"
                  >
                    {busy === `def-${theme.id}` ? "…" : "设为默认"}
                  </button>
                )}
                {!isBuiltin && (
                  <button
                    disabled={!!busy}
                    onClick={() => removeTheme(theme)}
                    className="ml-auto rounded-md px-2 py-1 text-[11px] text-neutral-400 hover:text-red-500 disabled:opacity-50"
                  >
                    {busy === `delete-${theme.id}` ? "…" : "删除"}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
