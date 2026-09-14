"use client";

import { useMemo } from "react";
import type { WechatThemeConfig } from "@/lib/types";
import { compileThemeConfig } from "@/lib/themeConfig";
import { renderWechatHtml } from "@/lib/wechatTheme";

/** 模板编辑器 / 模板卡片共用的示例文章：覆盖所有微信公众号组件。 */
export const SAMPLE_ARTICLE_MD = [
  "# 可解释的蛋白质结构预测",
  "",
  "> 导语：一句话说清这篇论文为什么值得读。",
  "",
  "## 研究背景",
  "",
  "本文提出了一种**可解释**的结构预测方法，在保持精度的同时显著降低算力开销，`推理速度` 提升约 2.3 倍。",
  "",
  "> [!NOTE]",
  "> 关键结论：模型在小样本场景下依然稳健。",
  "",
  "### 方法对比",
  "",
  "- 端到端训练，无需人工特征",
  "- 引入注意力可视化",
  "",
  "| 指标 | 基线 | 本文 |",
  "| --- | --- | --- |",
  "| 准确率 | 82.1% | 91.4% |",
  "| 参数量 | 340M | 210M |",
  "",
  "```python",
  "def predict(x):",
  "    return model(x)",
  "```",
  "",
  "![Figure 1](data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='600' height='360'><rect width='600' height='360' fill='%23e2e8f0'/><text x='300' y='195' font-size='30' fill='%2364748b' text-anchor='middle'>Figure</text></svg>)",
  "",
  "*图 1：模型整体架构示意图*",
  "",
  "---",
].join("\n");

/**
 * 手机宽度（默认 390px 内容区）公众号正文预览。
 *
 * 使用与发布同源的编译 + 渲染规则，因此模板编辑器的实时预览与最终推文一致：
 * 只用 inline style，不依赖外部 CSS。
 */
export function ThemePhonePreview({
  config,
  width = 390,
  bodyHeight,
  compact = false,
}: {
  config: WechatThemeConfig | undefined;
  width?: number;
  /** 正文区最大高度（px）；不传则自适应 */
  bodyHeight?: number;
  /** 卡片缩略图模式：隐藏手机状态栏，更紧凑 */
  compact?: boolean;
}) {
  const html = useMemo(() => {
    const styles = compileThemeConfig(config);
    return renderWechatHtml(SAMPLE_ARTICLE_MD, {
      id: "preview",
      name: "preview",
      styles,
    });
  }, [config]);

  return (
    <div
      className="mx-auto overflow-hidden rounded-2xl border border-neutral-200 bg-white shadow-sm"
      style={{ width, maxWidth: "100%" }}
    >
      {!compact && (
        <div className="shrink-0 h-8 px-4 flex items-center justify-between border-b border-neutral-100 bg-neutral-50 text-[10px] text-neutral-400 select-none">
          <span>9:41</span>
          <span className="tracking-[0.2em]">··· ▮</span>
        </div>
      )}
      <div
        className={`shrink-0 border-b border-neutral-100 ${
          compact ? "px-3 py-2" : "px-4 py-3"
        }`}
      >
        <div className="truncate text-[12px] font-medium text-neutral-800">
          PaperHub · 科研速递
        </div>
        {!compact && (
          <div className="mt-0.5 truncate text-[11px] text-neutral-400">
            可解释的蛋白质结构预测
          </div>
        )}
      </div>
      <div
        className="overflow-y-auto overflow-x-hidden"
        style={bodyHeight ? { maxHeight: bodyHeight } : undefined}
      >
        <div
          data-theme-body=""
          className={compact ? "px-3 py-2" : "px-4 py-4"}
          dangerouslySetInnerHTML={{ __html: html }}
        />
      </div>
    </div>
  );
}
