"""后端单元测试（无需数据库/Redis）。"""

import asyncio
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "demo" / "paper.pdf"


def run(coro):
    return asyncio.run(coro)


def test_mock_mineru_parses_demo_pdf():
    from app.services.mineru import MockMinerUService

    svc = MockMinerUService()
    result = run(svc.parse_pdf(DEMO))
    assert result.markdown.startswith("# ")
    assert len(result.images) == 3
    assert result.metadata["pages"] > 0
    assert "Figures" in result.markdown
    assert "images/" in result.markdown


def test_heuristic_figure_detection():
    from app.services.yolo import HeuristicFigureService

    svc = HeuristicFigureService()
    images = [("p1/images/a.png", 1), ("p1/images/b.png", 2)]
    out = run(svc.detect(images))
    assert len(out) == 2
    assert out[0].type == "figure"
    assert out[0].image_path == "p1/images/a.png"


def test_mock_llm_summary_and_article():
    from app.services.llm import MockLLMService

    llm = MockLLMService()
    md = "# Test Paper\n\n## Abstract\nThis is a test.\n\n## Figures\n![Figure 1](images/a.png)"
    system = f"<paper_markdown>\n{md}\n</paper_markdown>\n<figures>\n- Figure 1: foo\n</figures>"
    summary = run(
        llm.complete(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": "总结这篇论文"},
            ]
        )
    )
    assert "Test Paper" in summary

    article = run(
        llm.complete(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": "把这篇论文写成一篇微信公众号文章"},
            ]
        )
    )
    assert "Test Paper" in article
    assert "{{figure:0}}" in article


def test_wechat_formatter():
    from publishers.wechat.formatter import markdown_to_wechat_html

    md = "# Title\n\n> intro\n\n- a\n- b\n\n**bold** and `code`\n\n![x]({{figure:0}})"
    html = markdown_to_wechat_html(md, {"{{figure:0}}": "http://img"})
    assert "<h2>Title</h2>" in html
    assert "<blockquote>intro</blockquote>" in html
    assert "<ul>" in html
    assert "<strong>bold</strong>" in html
    assert '<img src="http://img"' in html


def test_skill_loader():
    from app.services.skill import list_skills, load_skill

    skills = list_skills()
    names = {s["name"] for s in skills}
    assert {"paper-summary", "figure-analysis", "wechat-article"} <= names

    s = load_skill("paper-summary")
    assert s is not None
    assert "研究背景" in s.prompt
