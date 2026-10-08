"""文章图片管理相关纯逻辑测试（无需数据库 / Redis / 微信接口）。"""

from app.core.config import settings  # noqa: F401  —— 注册仓库根目录到 sys.path

from app.api.v1.articles import _append_image, _image_ext
from app.schemas import ArticleUpdateRequest


def test_image_ext_accepts_supported_types():
    assert _image_ext("image/png", "x") == ".png"
    assert _image_ext("image/jpeg", "x") == ".jpg"
    assert _image_ext(None, "a.webp") == ".webp"
    assert _image_ext(None, "a.gif") == ".gif"
    assert _image_ext("application/pdf", "a.pdf") is None
    assert _image_ext("image/svg+xml", "a.svg") is None


def test_append_image_handles_none():
    assert _append_image(None, "k") == ["k"]
    assert _append_image(["a"], "b") == ["a", "b"]


def test_article_update_request_accepts_images():
    req = ArticleUpdateRequest(images=["a", "b"])
    assert req.model_dump(exclude_unset=True) == {"images": ["a", "b"]}
