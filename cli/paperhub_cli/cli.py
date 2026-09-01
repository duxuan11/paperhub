"""PaperHub CLI —— 通过 REST API 与后端通信。"""

from __future__ import annotations

import glob
import sys
import time

import typer
from rich.console import Console
from rich.table import Table

from .config import client, get_base_url, load_config, save_config

app = typer.Typer(help="PaperHub 科研论文 AI 工作台 CLI", no_args_is_help=True)
console = Console()


@app.command()
def upload(files: list[str] = typer.Argument(..., help="PDF 文件路径，支持 glob")):
    """上传论文 PDF（支持通配符）。"""
    paths: list[str] = []
    for f in files:
        paths.extend(glob.glob(f))
    if not paths:
        console.print("[red]未找到匹配的 PDF 文件[/red]")
        raise typer.Exit(1)

    with client() as c:
        for p in paths:
            if not p.lower().endswith(".pdf"):
                console.print(f"[yellow]跳过非 PDF: {p}[/yellow]")
                continue
            with open(p, "rb") as fh:
                r = c.post(
                    "/api/v1/papers/upload",
                    files={"file": (p.split("/")[-1], fh, "application/pdf")},
                )
            r.raise_for_status()
            d = r.json()
            console.print(f"[green]✓[/green] {p} -> {d['id']} (status={d['status']})")


@app.command("list")
def list_papers(
    status: str = typer.Option(None, help="按状态过滤"),
    query: str = typer.Option(None, help="搜索标题/文件名"),
):
    """列出论文。"""
    with client() as c:
        r = c.get("/api/v1/papers", params={"status": status, "query": query})
        r.raise_for_status()
        papers = r.json()
    table = Table(title="论文库")
    for col in ("ID", "标题", "年份", "期刊", "状态"):
        table.add_column(col)
    for p in papers:
        table.add_row(
            p["id"][:8],
            (p.get("title") or p.get("filename") or "未命名")[:40],
            str(p.get("year") or "-"),
            (p.get("journal") or "-")[:16],
            p["status"],
        )
    console.print(table)


@app.command()
def status(paper_id: str):
    """查看论文状态。"""
    with client() as c:
        p = c.get(f"/api/v1/papers/{paper_id}").json()
        jobs = c.get(f"/api/v1/papers/{paper_id}/jobs").json()
    console.print(f"[bold]{p.get('title') or p.get('filename')}[/bold]  ({paper_id})")
    console.print(f"状态: {p['status']}")
    if jobs:
        for j in jobs:
            icon = (
                "✓"
                if j["status"] == "SUCCESS"
                else ("●" if j["status"] == "RUNNING" else "✗")
            )
            console.print(
                f"  {icon} {j['job_type']}: {j['status']} {j.get('error') or ''}"
            )


def _wait_job(job_id: str, timeout: int = 120) -> dict:
    with client() as c:
        start = time.time()
        j: dict = {}
        while time.time() - start < timeout:
            j = c.get(f"/api/v1/jobs/{job_id}").json()
            if j["status"] in ("SUCCESS", "FAILED"):
                return j
            time.sleep(1)
        return j


@app.command()
def analyze(
    paper_id: str, skill: str = typer.Option("paper-summary", help="Skill 名称")
):
    """触发 AI 分析。"""
    with client() as c:
        r = c.post(f"/api/v1/papers/{paper_id}/analyze", json={"skill": skill})
        r.raise_for_status()
        job_id = r.json()["job_id"]
    console.print(f"已提交分析任务 {job_id[:8]}，等待完成...")
    j = _wait_job(job_id)
    if j["status"] == "SUCCESS":
        console.print("[green]分析完成[/green]")
    else:
        console.print(f"[red]分析失败: {j.get('error')}[/red]")


@app.command()
def summarize(paper_id: str):
    """触发分析并打印总结结果。"""
    with client() as c:
        r = c.post(
            f"/api/v1/papers/{paper_id}/analyze", json={"skill": "paper-summary"}
        )
        r.raise_for_status()
        job_id = r.json()["job_id"]
    j = _wait_job(job_id)
    if j["status"] != "SUCCESS":
        console.print(f"[red]分析失败: {j.get('error')}[/red]")
        raise typer.Exit(1)
    with client() as c:
        data = c.get(f"/api/v1/papers/{paper_id}/analysis").json()
    console.print(data.get("analysis") or "(无分析结果)")


@app.command()
def generate_wechat(
    paper_id: str,
    style: str = typer.Option("科研论文解读", help="模板风格"),
):
    """生成微信公众号文章。"""
    with client() as c:
        r = c.post(
            f"/api/v1/papers/{paper_id}/generate-wechat",
            json={"skill": "wechat-article", "style": style},
        )
        r.raise_for_status()
        job_id = r.json()["job_id"]
    console.print(f"已提交生成任务 {job_id[:8]}，等待完成...")
    j = _wait_job(job_id)
    if j["status"] != "SUCCESS":
        console.print(f"[red]生成失败: {j.get('error')}[/red]")
        raise typer.Exit(1)
    with client() as c:
        arts = c.get("/api/v1/articles", params={"paper_id": paper_id}).json()
    if arts:
        a = arts[0]
        console.print(f"[green]文章已生成[/green] id={a['id']}")
        console.print(f"标题: {a.get('title')}")


@app.command()
def publish_wechat(paper_id: str):
    """将论文最新文章发送到微信公众号草稿箱。"""
    with client() as c:
        arts = c.get("/api/v1/articles", params={"paper_id": paper_id}).json()
        if not arts:
            console.print("[red]未找到文章，请先 generate-wechat[/red]")
            raise typer.Exit(1)
        r = c.post("/api/v1/wechat/draft", json={"article_id": arts[0]["id"]})
        r.raise_for_status()
        d = r.json()
    console.print(f"[green]已提交草稿箱任务[/green] record_id={d['record_id']}")


@app.command()
def ask(paper_id: str, question: str):
    """针对指定论文提问（流式）。"""
    import httpx

    with client() as c:
        with c.stream(
            "POST", "/api/v1/chat", json={"message": question, "paper_id": paper_id}
        ) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if line.startswith("data:"):
                    import json

                    payload = json.loads(line[5:].strip())
                    if payload.get("delta"):
                        console.print(payload["delta"], end="")
    console.print()


@app.command()
def agent(message: str):
    """自由形式 Agent 提问（带入最近论文上下文）。"""
    import httpx

    with client() as c:
        with c.stream("POST", "/api/v1/agent", json={"message": message}) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if line.startswith("data:"):
                    import json

                    payload = json.loads(line[5:].strip())
                    if payload.get("delta"):
                        console.print(payload["delta"], end="")
    console.print()


@app.command()
def config(
    action: str = typer.Argument("show", help="show / set"),
    key: str = typer.Argument(None, help="api-key 或 base-url"),
    value: str = typer.Argument(None),
):
    """查看/设置配置。例如: paperhub config set api-key xxx"""
    cfg = load_config()
    if action == "show":
        console.print(f"base_url: {get_base_url()}")
        console.print(f"api_key: {'已设置' if cfg.get('api_key') else '未设置'}")
        return
    if action == "set":
        if key not in ("api-key", "base-url"):
            console.print("[red]key 必须是 api-key 或 base-url[/red]")
            raise typer.Exit(1)
        if value is None:
            console.print("[red]缺少 value[/red]")
            raise typer.Exit(1)
        cfg["api_key" if key == "api-key" else "base_url"] = value
        save_config(cfg)
        console.print(f"[green]已设置 {key}[/green]")
        return
    console.print(f"[red]未知操作: {action}[/red]")


if __name__ == "__main__":
    app()
