"""PaperHub 核心配置。所有配置通过环境变量注入。"""

import sys
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 仓库根目录（backend/app/core/config.py -> 上溯三级）
ROOT = Path(__file__).resolve().parents[3]

# 确保仓库根目录在 sys.path，使 publishers / skills 等顶层包可被导入
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 应用
    app_name: str = "PaperHub"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    cors_origins: str = "http://localhost:3000,http://localhost"
    data_dir: str = str(ROOT / "data")
    skills_dir: str = str(ROOT / "skills")

    # 数据库
    database_url: str = "postgresql+asyncpg://paperhub:paperhub@localhost:5432/paperhub"
    redis_url: str = "redis://localhost:6379/0"

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "paperhub"
    minio_secret_key: str = "paperhub-secret"
    minio_secure: bool = False
    minio_bucket: str = "paperhub"

    # MinerU
    mineru_api_url: str = ""
    mineru_api_key: str = ""

    # YOLO
    yolo_model_path: str = ""
    yolo_enabled: bool = False

    # LLM (OpenAI-compatible)
    openai_api_key: str = ""
    openai_base_url: str = "https://api.deepseek.com"
    openai_model: str = "deepseek-chat"
    llm_timeout: int = 120

    # 微信公众号
    wechat_app_id: str = ""
    wechat_app_secret: str = ""

    # 自身鉴权
    paperhub_api_key: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def data_path(self) -> Path:
        return Path(self.data_dir)

    @property
    def skills_path(self) -> Path:
        return Path(self.skills_dir)

    @property
    def auth_enabled(self) -> bool:
        return bool(self.paperhub_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
