"""LLM 客户端（OpenAI-compatible）+ Mock 实现。

真实实现调用任意 OpenAI-compatible /chat/completions（DeepSeek/OpenAI/Ollama...）。
未配置 API Key 时使用 MockLLMService，基于传入的论文上下文生成确定性回复，
保证 Demo 无需 Key 也能演示。
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator

import httpx

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("llm")


class LLMService:
    async def complete(self, messages: list[dict], **kw) -> str:
        raise NotImplementedError

    async def stream_complete(self, messages: list[dict], **kw) -> AsyncIterator[str]:
        text = await self.complete(messages, **kw)
        yield text


def get_llm_service() -> LLMService:
    if settings.openai_api_key:
        return RealLLMService(
            settings.openai_base_url, settings.openai_api_key, settings.openai_model
        )
    return MockLLMService()


def llm_mode() -> str:
    return "real" if settings.openai_api_key else "mock"


class RealLLMService(LLMService):
    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _endpoint(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"

    async def complete(self, messages: list[dict], **kw) -> str:
        payload = {"model": self.model, "messages": messages, "stream": False}
        payload.update(kw)
        async with httpx.AsyncClient(timeout=settings.llm_timeout) as client:
            resp = await client.post(
                self._endpoint(), headers=self._headers(), json=payload
            )
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"]

    async def stream_complete(self, messages: list[dict], **kw) -> AsyncIterator[str]:
        payload = {"model": self.model, "messages": messages, "stream": True}
        payload.update(kw)
        async with httpx.AsyncClient(timeout=settings.llm_timeout) as client:
            async with client.stream(
                "POST", self._endpoint(), headers=self._headers(), json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[len("data:") :].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0]["delta"].get("content")
                        if delta:
                            yield delta
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue


class MockLLMService(LLMService):
    """无 Key 时的确定性 Mock，基于上下文生成贴近论文内容的回复。"""

    async def complete(self, messages: list[dict], **kw) -> str:
        user_text = messages[-1]["content"] if messages else ""
        system = "\n".join(
            m.get("content", "") for m in messages if m.get("role") == "system"
        )
        return build_mock_response(user_text, system)

    async def stream_complete(self, messages: list[dict], **kw) -> AsyncIterator[str]:
        text = await self.complete(messages, **kw)
        for i in range(0, len(text), 24):
            yield text[i : i + 24]


# ---- Mock 内容生成 ----


def _extract_markdown(system: str) -> str:
    m = re.search(r"<paper_markdown>\n?(.*?)</paper_markdown>", system, re.S)
    if m:
        return m.group(1)
    # 兜底：从“Markdown：”标记后提取正文
    m2 = re.search(r"(?:论文\s*Markdown|Markdown)[：:]\s*\n?(.*)", system, re.S)
    if m2:
        return m2.group(1)
    return ""


def _extract_figures(system: str) -> list[str]:
    m = re.search(r"<figures>\n?(.*?)</figures>", system, re.S)
    if not m:
        return []
    return [ln.strip() for ln in m.group(1).splitlines() if ln.strip()]


def _headings(md: str) -> list[str]:
    return [
        ln.strip().lstrip("#").strip() for ln in md.splitlines() if ln.startswith("#")
    ]


def _title(md: str) -> str:
    for ln in md.splitlines():
        if ln.startswith("# "):
            return ln[2:].strip()
    return "本文"


def build_mock_response(user_text: str, system: str) -> str:
    combined = system + "\n\n" + user_text
    md = _extract_markdown(combined)
    title = (
        _title(md) if md else _title(system) if _extract_markdown(system) else "本文"
    )
    headings = _headings(md)
    figures = _extract_figures(combined)
    low = user_text.lower()

    # 公众号文章
    if (
        any(k in user_text for k in ("公众号", "微信", "文章"))
        or "generate_article" in system
    ):
        return _mock_article(md, title, headings, figures)
    # Figure 分析
    if any(k in user_text for k in ("figure", "fig", "图", "Figure")):
        return _mock_figure_analysis(md, title, figures)
    # 总结
    if any(
        k in user_text
        for k in ("总结", "摘要", "总结这篇", "summary", "概述", "核心创新", "创新")
    ):
        return _mock_summary(md, title, headings)
    # 默认：通用问答式总结
    return _mock_summary(md, title, headings)


def _mock_summary(md: str, title: str, headings: list[str]) -> str:
    h = "、".join(headings[1:5]) if len(headings) > 1 else "摘要、方法、结果、讨论"
    return f"""# {title} —— 论文总结

## 1. 研究背景
这篇论文聚焦于「{title}」所涉及的研究问题，属于当前领域的重要方向。

## 2. 核心创新
论文提出了新的方法/框架来推进该问题（详见正文与 Figure 分析）。

## 3. 论文结构
论文主要包含以下章节：{h}。

## 4. 主要结果
- 论文通过实验验证了所提方法的有效性。
- 具体数值与结论请参见论文正文中的 Results 章节与各 Figure。

## 5. 说明
> ⚠️ 当前运行在 Mock 模式（未配置 LLM API Key）。
> 配置 `OPENAI_API_KEY` 后将由真实模型（如 DeepSeek）生成精确分析。
>
> 论文未提供相关信息的部分请以原文为准。
"""


def _mock_figure_analysis(md: str, title: str, figures: list[str]) -> str:
    if not figures:
        return "论文当前未解析到 Figure 图片（未提供相关信息）。"
    lines = [f"# {title} —— Figure 分析", ""]
    for i, f in enumerate(figures, 1):
        lines.append(f"## Figure {i}")
        lines.append(f"- **Figure 编号**：Figure {i}")
        lines.append("- **实验目的**：展示论文中的关键结果/方法（请以原图为准）")
        lines.append(
            "- **主要结果**：论文未提供相关信息（Mock 模式，无视觉模型直接识别图像内容）"
        )
        lines.append("- **作者意图**：通过该图支撑论文核心结论")
        lines.append("")
    lines.append(
        "> ⚠️ 当前为 Mock 模式，未对图片做真实视觉识别。配置 LLM 后可由多模态模型分析。"
    )
    return "\n".join(lines)


def _mock_article(md: str, title: str, headings: list[str], figures: list[str]) -> str:
    fig_block = ""
    if figures:
        fig_block = "\n\n".join(
            f"![Figure {i}]({{{{figure:{i - 1}}}}})" for i in range(1, len(figures) + 1)
        )
    return f"""# {title}｜一文读懂这篇论文

> **导语**：本文将带你快速读懂「{title}」的核心思想、方法与结果。

## 研究背景
{title} 所属的研究方向近年来受到广泛关注，作者针对其中尚未解决的关键问题展开了研究。

## 核心创新
论文提出了新的方法与视角，为领域提供了有价值的思路。

## 方法与实验
论文设计了系统的实验来验证所提方法，相关章节包括：{"、".join(headings[1:5]) if len(headings) > 1 else "方法、实验、结果"}。

{("## 关键图示\n\n" + fig_block) if fig_block else ""}

## 结论与启发
这篇论文为后续研究提供了重要参考。更细节的数据与讨论请参考原文。

---

**论文来源**：{title}
**生成说明**：本文由 PaperHub AI 生成（当前为 Mock 模式，配置 LLM 后质量更高），仅供阅读参考，具体以原文为准。
"""
