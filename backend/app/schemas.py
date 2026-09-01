"""Pydantic 请求/响应模型。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---- Paper ----
class PaperOut(BaseModel):
    id: str
    title: str | None
    authors: list[str] | None
    abstract: str | None
    doi: str | None
    journal: str | None
    year: int | None
    tags: list[str] | None
    filename: str | None
    status: str
    created_at: datetime | None
    updated_at: datetime | None

    class Config:
        from_attributes = True


class FigureOut(BaseModel):
    id: str
    paper_id: str
    figure_number: int | None
    image_path: str
    caption: str | None
    bbox: list | None
    type: str | None
    page: int | None
    created_at: datetime | None

    class Config:
        from_attributes = True


class JobOut(BaseModel):
    id: str
    paper_id: str | None
    job_type: str
    status: str
    progress: int
    error: str | None
    created_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None

    class Config:
        from_attributes = True


class ArticleOut(BaseModel):
    id: str
    paper_id: str | None
    title: str | None
    summary: str | None
    content: str | None
    html: str | None
    style: str | None
    skill: str | None
    images: list | None
    references: list | None
    status: str
    created_at: datetime | None
    updated_at: datetime | None

    class Config:
        from_attributes = True


class PublishRecordOut(BaseModel):
    id: str
    article_id: str | None
    platform: str
    status: str
    external_id: str | None
    error: str | None
    created_at: datetime | None
    published_at: datetime | None

    class Config:
        from_attributes = True


# ---- Requests ----
class GenerateArticleRequest(BaseModel):
    skill: str = "wechat-article"
    style: str = "科研论文解读"
    extra_instructions: str | None = None


class AnalyzeRequest(BaseModel):
    skill: str = "paper-summary"


class ChatRequest(BaseModel):
    message: str
    paper_id: str | None = None
    skill: str | None = None
    history: list[dict[str, str]] = Field(default_factory=list)


class ChatChunk(BaseModel):
    delta: str = ""
    done: bool = False


class ArticleUpdateRequest(BaseModel):
    title: str | None = None
    summary: str | None = None
    content: str | None = None
    html: str | None = None


class PublishRequest(BaseModel):
    platform: str = "wechat"
    publish: bool = False


class WeChatRequest(BaseModel):
    article_id: str
    publish: bool = False


class ArticleActionRequest(BaseModel):
    action: str  # polish / shorten / expand / regenerate
    instruction: str | None = None
    style: str | None = None


class PaperMeta(BaseModel):
    title: str | None = None
    authors: list[str] | None = None
    doi: str | None = None
    journal: str | None = None
    year: int | None = None
    tags: list[str] | None = None
    abstract: str | None = None


class TaskEnqueueOut(BaseModel):
    job_id: str
    paper_id: str


class WeChatDraftOut(BaseModel):
    record_id: str
    article_id: str
    external_id: str | None
    status: str
    mock: bool


class HealthOut(BaseModel):
    status: str
    version: str
    auth_enabled: bool
    llm_mode: str
    mineru_mode: str
    yolo_mode: str
    wechat_mode: str
