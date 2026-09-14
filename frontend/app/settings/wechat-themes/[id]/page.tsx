"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { apiGet, apiPost, apiPut } from "@/lib/api";
import type {
  WechatTheme,
  WechatThemeColors,
  WechatThemeConfig,
  WechatThemeTypography,
} from "@/lib/types";
import {
  COMPONENT_GROUPS,
  DEFAULT_THEME_CONFIG,
  compileThemeConfig,
  mergeThemeConfig,
} from "@/lib/themeConfig";
import { ThemePhonePreview } from "@/components/ThemePhonePreview";

const COLOR_FIELDS: { key: keyof WechatThemeColors; label: string }[] = [
  { key: "primary", label: "主色 Primary" },
  { key: "secondary", label: "次要色 Secondary" },
  { key: "text", label: "正文色 Text" },
  { key: "muted", label: "弱化色 Muted" },
  { key: "background", label: "背景色 Background" },
  { key: "border", label: "边框色 Border" },
];

const TYPO_FIELDS: {
  key: keyof WechatThemeTypography;
  label: string;
  hint?: string;
}[] = [
  { key: "bodySize", label: "正文字号", hint: "如 15px" },
  { key: "bodyLineHeight", label: "正文行高", hint: "如 1.8" },
  { key: "heading1Size", label: "一级标题", hint: "如 24px" },
  { key: "heading2Size", label: "二级标题", hint: "如 19px" },
  { key: "heading3Size", label: "三级标题", hint: "如 17px" },
  { key: "captionSize", label: "图注字号", hint: "如 13px" },
];

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mt-6 rounded-xl border border-neutral-200 bg-white">
      <div className="border-b border-neutral-100 px-5 py-3 text-[13px] font-semibold text-neutral-800">
        {title}
      </div>
      <div className="px-5 py-4">{children}</div>
    </section>
  );
}

export default function WechatThemeEditorPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params?.id ?? "new";
  const isNew = id === "new";

  const [theme, setTheme] = useState<WechatTheme | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [config, setConfig] = useState<WechatThemeConfig>(DEFAULT_THEME_CONFIG);
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const readonly = !isNew && !!theme?.is_builtin;

  const load = useCallback(async () => {
    if (isNew) {
      setTheme(null);
      setName("");
      setDescription("");
      setConfig(mergeThemeConfig(DEFAULT_THEME_CONFIG));
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const t = await apiGet<WechatTheme>(`/wechat/themes/${id}`);
      setTheme(t);
      setName(t.name);
      setDescription(t.description || "");
      setConfig(mergeThemeConfig(t.config));
      setError("");
    } catch (e) {
      setError(`模板加载失败：${e}`);
    } finally {
      setLoading(false);
    }
  }, [id, isNew]);

  useEffect(() => {
    load();
  }, [load]);

  const compiled = useMemo(() => compileThemeConfig(config), [config]);

  function setColor(key: keyof WechatThemeColors, value: string) {
    setConfig((prev) => ({ ...prev, colors: { ...prev.colors, [key]: value } }));
  }

  function setTypo(key: keyof WechatThemeTypography, value: string) {
    setConfig((prev) => ({
      ...prev,
      typography: { ...prev.typography, [key]: value },
    }));
  }

  function setComponent(key: string, prop: string, value: string) {
    setConfig((prev) => {
      const components = { ...prev.components };
      const current = { ...(components[key] ?? {}) };
      if (value) current[prop] = value;
      else delete current[prop];
      if (Object.keys(current).length) components[key] = current;
      else delete components[key];
      return { ...prev, components };
    });
  }

  /** 显示当前实际生效的样式值（未覆盖时取编译默认值）。 */
  function effective(key: string, prop: string): string {
    return config.components?.[key]?.[prop] ?? compiled[key]?.[prop] ?? "";
  }

  async function save() {
    if (!name.trim()) {
      alert("请填写模板名称");
      return;
    }
    setSaving(true);
    try {
      const payload = { name: name.trim(), description, config };
      if (isNew) {
        await apiPost<WechatTheme>("/wechat/themes", payload);
      } else {
        await apiPut<WechatTheme>(`/wechat/themes/${id}`, payload);
      }
      router.push("/settings");
    } catch (e) {
      alert(`保存失败：${e}`);
    } finally {
      setSaving(false);
    }
  }

  async function duplicateToCustom() {
    try {
      const copy = await apiPost<WechatTheme>(`/wechat/themes/${id}/duplicate`);
      router.replace(`/settings/wechat-themes/${copy.id}`);
    } catch (e) {
      alert(`复制失败：${e}`);
    }
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="flex items-center gap-3 border-b border-neutral-200 bg-white px-6 py-3">
        <Link href="/settings" className="text-[13px] text-neutral-400 hover:text-neutral-600">
          ← 返回设置
        </Link>
        <span className="text-[15px] font-semibold text-neutral-900">
          {isNew ? "新建推文模板" : readonly ? "查看推文模板" : "编辑推文模板"}
        </span>
        {theme?.is_builtin && (
          <span className="rounded bg-neutral-200 px-1.5 py-0.5 text-[10px] font-medium text-neutral-600">
            Built-in
          </span>
        )}
        <span className="flex-1" />
        {readonly && (
          <button
            onClick={duplicateToCustom}
            className="rounded-lg border border-brand-200 px-3 py-1.5 text-[12px] text-brand-600"
          >
            复制为自定义模板
          </button>
        )}
        {!readonly && (
          <button
            onClick={save}
            disabled={saving}
            className="rounded-lg bg-brand-600 px-3 py-1.5 text-[12px] text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {saving ? "保存中…" : isNew ? "创建模板" : "保存"}
          </button>
        )}
      </div>

      {loading && <p className="p-6 text-[13px] text-neutral-400">加载中…</p>}
      {error && <p className="p-6 text-[13px] text-red-500">{error}</p>}

      {!loading && !error && (
        <div className="mx-auto grid max-w-[1180px] grid-cols-1 gap-6 px-6 py-6 lg:grid-cols-[minmax(0,1fr)_440px]">
          {/* 左侧：设计变量表单 */}
          <div className="min-w-0">
            {readonly && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-[12px] text-amber-700">
                内置模板不可直接编辑。如需调整，请点击右上角「复制为自定义模板」。
              </div>
            )}

            <Section title="基础">
              <div className="grid gap-3">
                <label className="grid gap-1">
                  <span className="text-[12px] text-neutral-500">模板名称</span>
                  <input
                    value={name}
                    disabled={readonly}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="例如：Academic Blue"
                    className="rounded-md border border-neutral-200 px-2.5 py-1.5 text-[13px] focus:border-brand-300 focus:outline-none disabled:bg-neutral-50"
                  />
                </label>
                <label className="grid gap-1">
                  <span className="text-[12px] text-neutral-500">描述</span>
                  <input
                    value={description}
                    disabled={readonly}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="适合科研论文、AI、生物医学文章"
                    className="rounded-md border border-neutral-200 px-2.5 py-1.5 text-[13px] focus:border-brand-300 focus:outline-none disabled:bg-neutral-50"
                  />
                </label>
              </div>
            </Section>

            <Section title="颜色 Colors">
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                {COLOR_FIELDS.map((field) => (
                  <label key={field.key} className="grid gap-1">
                    <span className="text-[12px] text-neutral-500">{field.label}</span>
                    <span className="flex items-center gap-2">
                      <input
                        type="color"
                        value={config.colors[field.key]}
                        disabled={readonly}
                        onChange={(e) => setColor(field.key, e.target.value)}
                        className="h-7 w-9 cursor-pointer rounded border border-neutral-200 disabled:opacity-50"
                      />
                      <input
                        value={config.colors[field.key]}
                        disabled={readonly}
                        onChange={(e) => setColor(field.key, e.target.value)}
                        data-testid={`color-${field.key}`}
                        className="w-full rounded-md border border-neutral-200 px-2 py-1 text-[12px] focus:border-brand-300 focus:outline-none disabled:bg-neutral-50"
                      />
                    </span>
                  </label>
                ))}
              </div>
            </Section>

            <Section title="字体排版 Typography">
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                {TYPO_FIELDS.map((field) => (
                  <label key={field.key} className="grid gap-1">
                    <span className="text-[12px] text-neutral-500">{field.label}</span>
                    <input
                      value={String(config.typography[field.key] ?? "")}
                      disabled={readonly}
                      onChange={(e) => setTypo(field.key, e.target.value)}
                      placeholder={field.hint}
                      className="rounded-md border border-neutral-200 px-2 py-1 text-[12px] focus:border-brand-300 focus:outline-none disabled:bg-neutral-50"
                    />
                  </label>
                ))}
              </div>
            </Section>

            <Section title="文章组件 Components">
              <div className="grid gap-5">
                {COMPONENT_GROUPS.map((group) => (
                  <div key={group.label}>
                    <div className="mb-1.5 flex items-baseline gap-2">
                      <span className="text-[12px] font-medium text-neutral-700">
                        {group.label}
                      </span>
                      <span className="text-[11px] text-neutral-400">{group.hint}</span>
                    </div>
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                      {group.fields.map((field) => {
                        const value = effective(field.key, field.prop);
                        return (
                          <label key={`${field.key}.${field.prop}`} className="grid gap-1">
                            <span className="text-[11px] text-neutral-400">
                              {field.label}
                            </span>
                            {field.type === "color" ? (
                              <span className="flex items-center gap-2">
                                <input
                                  type="color"
                                  value={/^#[0-9a-fA-F]{6}$/.test(value) ? value : "#000000"}
                                  disabled={readonly}
                                  onChange={(e) =>
                                    setComponent(field.key, field.prop, e.target.value)
                                  }
                                  className="h-7 w-9 cursor-pointer rounded border border-neutral-200 disabled:opacity-50"
                                />
                                <input
                                  value={value}
                                  disabled={readonly}
                                  onChange={(e) =>
                                    setComponent(field.key, field.prop, e.target.value)
                                  }
                                  className="w-full rounded-md border border-neutral-200 px-2 py-1 text-[12px] focus:border-brand-300 focus:outline-none disabled:bg-neutral-50"
                                />
                              </span>
                            ) : (
                              <input
                                value={value}
                                disabled={readonly}
                                onChange={(e) =>
                                  setComponent(field.key, field.prop, e.target.value)
                                }
                                className="rounded-md border border-neutral-200 px-2 py-1 text-[12px] focus:border-brand-300 focus:outline-none disabled:bg-neutral-50"
                              />
                            )}
                          </label>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </Section>
          </div>

          {/* 右侧：390px 手机宽度实时预览 */}
          <div className="min-w-0">
            <div className="sticky top-6">
              <div className="mb-2 flex items-center gap-2">
                <span className="text-[12px] font-medium text-neutral-500">
                  实时预览
                </span>
                <span className="text-[11px] text-neutral-400">
                  390px 移动端内容区 · 与发布同源
                </span>
              </div>
              <ThemePhonePreview config={config} width={390} bodyHeight={660} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
