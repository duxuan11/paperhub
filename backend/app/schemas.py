"""Pydantic 请求/响应模型。"""

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


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
    author: str | None = None
    theme: str | None = None
    cover_image: str | None = None
    images: list | None
    references: list | None
    status: str
    created_at: datetime | None
    updated_at: datetime | None

    class Config:
        from_attributes = True


_HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_CSS_SIZE_RE = re.compile(r"^\d+(?:\.\d+)?(?:px|em|rem|%)?$")


class WeChatThemeColors(BaseModel):
    """主题配色变量（全部为十六进制颜色）。"""

    primary: str = "#2563EB"
    secondary: str = "#64748B"
    text: str = "#1E293B"
    muted: str = "#64748B"
    background: str = "#FFFFFF"
    border: str = "#E2E8F0"

    @field_validator("primary", "secondary", "text", "muted", "background", "border")
    @classmethod
    def _validate_hex(cls, value: str) -> str:
        if not isinstance(value, str) or not _HEX_COLOR_RE.match(value.strip()):
            raise ValueError("颜色必须是 #RGB 或 #RRGGBB 十六进制格式")
        return value.strip()


class WeChatThemeTypography(BaseModel):
    """主题字体排版变量（字号 / 行高）。"""

    fontFamily: str | None = None
    bodySize: str = "15px"
    bodyLineHeight: str = "1.8"
    heading1Size: str = "24px"
    heading2Size: str = "19px"
    heading3Size: str = "17px"
    captionSize: str = "13px"

    @field_validator(
        "bodySize",
        "bodyLineHeight",
        "heading1Size",
        "heading2Size",
        "heading3Size",
        "captionSize",
    )
    @classmethod
    def _validate_size(cls, value: str) -> str:
        if not isinstance(value, str) or not _CSS_SIZE_RE.match(value.strip()):
            raise ValueError("字号 / 行高必须是数字，可带 px / em / rem / % 单位")
        return value.strip()


class WeChatThemeConfig(BaseModel):
    """主题设计变量：配色 + 字体排版 + 组件级 CSS 覆盖。"""

    colors: WeChatThemeColors = Field(default_factory=WeChatThemeColors)
    typography: WeChatThemeTypography = Field(default_factory=WeChatThemeTypography)
    components: dict[str, dict[str, str]] = Field(default_factory=dict)


class WechatThemeOut(BaseModel):
    """公众号主题（含设计变量与编译后的 inline 样式）。"""

    id: str
    name: str
    description: str = ""
    config: WeChatThemeConfig = Field(default_factory=WeChatThemeConfig)
    styles: dict[str, dict[str, str]] = Field(default_factory=dict)
    is_builtin: bool = False
    is_default: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class WeChatThemeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    config: WeChatThemeConfig | None = None
    is_default: bool = False


class WeChatThemeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    config: WeChatThemeConfig | None = None


class WeChatThemeDuplicate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)


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
    skill: str | None = None


class SkillDetail(BaseModel):
    name: str
    description: str = ""
    tools: list[str] = Field(default_factory=list)
    prompt: str = ""


class AnalysisPromptOut(BaseModel):
    skill: str
    prompt: str = ""
    default_skill: str
    default_prompt: str
    skills: list[SkillDetail] = Field(default_factory=list)


class AnalysisPromptUpdate(BaseModel):
    skill: str | None = None
    prompt: str | None = None


# ---- AI 分析（Skills + Model + Prompt） ----
class AIAnalysisConfigOut(BaseModel):
    paper_id: str
    enabled: bool = True
    model: str = ""
    selected_skills: list[str] = Field(default_factory=list)
    custom_prompt: str = ""
    default_model: str = ""
    default_skills: list[str] = Field(default_factory=list)
    available_skills: list[SkillDetail] = Field(default_factory=list)
    updated_at: datetime | None = None


class AIAnalysisConfigUpdate(BaseModel):
    enabled: bool | None = None
    model: str | None = None
    selected_skills: list[str] | None = None
    custom_prompt: str | None = None


class AIAnalysisRunRequest(AIAnalysisConfigUpdate):
    """可选的运行参数：先保存这些配置，再执行分析。"""


class AIAnalysisResultOut(BaseModel):
    paper_id: str
    skill: str
    content: str = ""
    model: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class AIAnalysisOut(BaseModel):
    paper_id: str
    parsed: bool = False
    config: AIAnalysisConfigOut
    results: list[AIAnalysisResultOut] = Field(default_factory=list)


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
    author: str | None = None
    theme: str | None = None
    cover_image: str | None = None


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
