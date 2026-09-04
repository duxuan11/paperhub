"""PaperHub MCP Server —— 让 Open WebUI / Claude 等 Agent 访问论文库。

通过 stdio 传输运行；配置环境变量 PAPERHUB_API_URL / PAPERHUB_API_KEY 指向后端。
"""

from __future__ import annotations

import json

from mcp.server.mcpserver import MCPServer

from tools import client

mcp = MCPServer("PaperHub")


def _fmt_papers(papers: list[dict]) -> str:
    rows = []
    for p in papers:
        rows.append(
            f"- [{p['id']}] {p.get('title') or p.get('filename') or '未命名'} "
            f"(status={p.get('status')}, year={p.get('year')}, journal={p.get('journal')})"
        )
    return "\n".join(rows) or "无结果"


@mcp.tool()
async def search_papers(query: str = "", status: str = "") -> str:
    """搜索/列出论文。query 匹配标题或文件名，status 可按论文状态过滤。"""
    papers = client.get("/api/v1/papers", query=query or None, status=status or None)
    return _fmt_papers(papers)


@mcp.tool()
async def get_paper(paper_id: str) -> str:
    """获取单篇论文的基本元数据。"""
    return json.dumps(
        client.get(f"/api/v1/papers/{paper_id}"), ensure_ascii=False, indent=2
    )


@mcp.tool()
async def get_paper_markdown(paper_id: str) -> str:
    """获取论文解析后的 Markdown 全文。"""
    data = client.get(f"/api/v1/papers/{paper_id}/markdown")
    return data.get("markdown", "")


@mcp.tool()
async def get_paper_metadata(paper_id: str) -> str:
    """获取论文元数据（标题/作者/DOI/年份等）。"""
    return json.dumps(
        client.get(f"/api/v1/papers/{paper_id}"), ensure_ascii=False, indent=2
    )


@mcp.tool()
async def get_paper_figures(paper_id: str) -> str:
    """列出论文检测到的所有 Figure 及其编号、类型、图注。"""
    figs = client.get(f"/api/v1/papers/{paper_id}/figures")
    rows = [
        f"- Figure {f.get('figure_number')} (type={f.get('type')}, page={f.get('page')}): "
        f"{f.get('caption') or '无图注'} [image_path={f.get('image_path')}]"
        for f in figs
    ]
    return "\n".join(rows) or "无 Figure"


@mcp.tool()
async def get_figure(figure_id: str) -> str:
    """获取单张 Figure 的元信息（不含图片二进制，供文本分析）。"""
    # figure 通过 paper 的列表暴露；此处返回 id 以便后续扩展
    return json.dumps(
        {"figure_id": figure_id, "note": "请使用 get_paper_figures 获取图片列表与路径"},
        ensure_ascii=False,
    )


@mcp.tool()
async def search_paper_content(paper_id: str, keyword: str) -> str:
    """在指定论文的 Markdown 中搜索关键词，返回匹配上下文。"""
    md = client.get(f"/api/v1/papers/{paper_id}/markdown").get("markdown", "")
    lines = md.splitlines()
    hits = []
    for i, ln in enumerate(lines):
        if keyword.lower() in ln.lower():
            ctx = "\n".join(lines[max(0, i - 1) : i + 2])
            hits.append(f"--- 第 {i + 1} 行 ---\n{ctx}")
            if len(hits) >= 10:
                break
    return "\n\n".join(hits) or "未找到匹配内容"


@mcp.tool()
async def analyze_paper(paper_id: str, skill: str = "paper-summary") -> str:
    """触发论文 AI 分析（异步任务），返回 job_id。"""
    resp = client.post(f"/api/v1/papers/{paper_id}/analyze", {"skill": skill})
    return f"已提交分析任务: job_id={resp.get('job_id')}"


@mcp.tool()
async def generate_wechat_article(paper_id: str, style: str = "科研论文解读") -> str:
    """为论文生成微信公众号文章（异步任务），返回 job_id。"""
    resp = client.post(
        f"/api/v1/papers/{paper_id}/generate-wechat",
        {"skill": "wechat-article", "style": style},
    )
    return f"已提交公众号文章生成任务: job_id={resp.get('job_id')}"


@mcp.tool()
async def publish_wechat(article_id: str) -> str:
    """将文章发送到微信公众号草稿箱（安全设计：不直接发布）。"""
    resp = client.post(f"/api/v1/wechat/draft", {"article_id": article_id})
    return f"已提交草稿箱任务: record_id={resp.get('record_id')}, status={resp.get('status')}"


if __name__ == "__main__":
    mcp.run()
