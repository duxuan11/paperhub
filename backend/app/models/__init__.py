"""数据模型（SQLAlchemy 2.x）。"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _uuid() -> str:
    return uuid.uuid4().hex


class PaperStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    PARSING = "PARSING"
    PARSED = "PARSED"
    FIGURE_DETECTING = "FIGURE_DETECTING"
    READY = "READY"
    ANALYZING = "ANALYZING"
    ANALYZED = "ANALYZED"
    CONTENT_GENERATED = "CONTENT_GENERATED"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class ArticleStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    GENERATED = "GENERATED"
    SENT_TO_PLATFORM = "SENT_TO_PLATFORM"
    PUBLISHED = "PUBLISHED"


class PublishStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    authors: Mapped[list | None] = mapped_column(JSON, nullable=True)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    doi: Mapped[str | None] = mapped_column(String(256), nullable=True)
    journal: Mapped[str | None] = mapped_column(String(256), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    pdf_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    markdown_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    metadata_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    analysis_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[PaperStatus] = mapped_column(
        Enum(PaperStatus), default=PaperStatus.UPLOADED, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    figures: Mapped[list["Figure"]] = relationship(
        back_populates="paper", cascade="all, delete-orphan"
    )
    jobs: Mapped[list["Job"]] = relationship(
        back_populates="paper", cascade="all, delete-orphan"
    )
    articles: Mapped[list["Article"]] = relationship(
        back_populates="paper", cascade="all, delete-orphan"
    )


class Figure(Base):
    __tablename__ = "figures"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    paper_id: Mapped[str] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), index=True
    )
    figure_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    bbox: Mapped[list | None] = mapped_column(JSON, nullable=True)
    type: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )  # figure/table/equation
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    paper: Mapped["Paper"] = relationship(back_populates="figures")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    paper_id: Mapped[str | None] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), index=True, nullable=True
    )
    job_type: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # parse/detect_figures/analyze/generate_wechat/publish_wechat
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus), default=JobStatus.PENDING, nullable=False
    )
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    paper: Mapped["Paper"] = relationship(back_populates="jobs")


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    paper_id: Mapped[str | None] = mapped_column(
        ForeignKey("papers.id", ondelete="SET NULL"), index=True, nullable=True
    )
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)  # markdown
    html: Mapped[str | None] = mapped_column(Text, nullable=True)
    style: Mapped[str | None] = mapped_column(String(64), nullable=True)
    skill: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 公众号发布配置（新增，全部 nullable，兼容旧数据）
    author: Mapped[str | None] = mapped_column(String(128), nullable=True)
    theme: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cover_image: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    images: Mapped[list | None] = mapped_column(JSON, nullable=True)
    references: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[ArticleStatus] = mapped_column(
        Enum(ArticleStatus), default=ArticleStatus.DRAFT, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    paper: Mapped["Paper"] = relationship(back_populates="articles")
    publish_records: Mapped[list["PublishRecord"]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )


class AppSetting(Base):
    """键值型应用配置（AI 分析提示词等，可在设置页热更新）。"""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PublishRecord(Base):
    __tablename__ = "publish_records"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    article_id: Mapped[str | None] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), index=True, nullable=True
    )
    platform: Mapped[str] = mapped_column(String(32), default="wechat")
    status: Mapped[PublishStatus] = mapped_column(
        Enum(PublishStatus), default=PublishStatus.PENDING, nullable=False
    )
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    article: Mapped["Article"] = relationship(back_populates="publish_records")


class WeChatArticleTheme(Base):
    """微信公众号推文排版主题（Theme）。

    ``config`` 存的是**设计变量**（colors / typography / components），由
    ``publishers.wechat.theme_config.compile_styles`` 编译成渲染器使用的
    inline style；内置主题由 ``publishers.wechat.themes.BUILTIN_THEMES`` 在
    启动时幂等写入（``is_builtin=True``），用户可复制后编辑自定义主题。
    """

    __tablename__ = "wechat_article_themes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_builtin: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
