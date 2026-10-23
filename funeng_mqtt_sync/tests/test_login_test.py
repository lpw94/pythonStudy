"""验证码下载 + 识别的单元测试（不联网、不加载 OCR 模型）。

测的是两条容易静默出错的规则：

1. **服务端返回的不是图片时必须报错**，不能当成图片存盘。
   实测踩过：接口缺 Token 时返回 HTTP 200 + {"code":20000,"message":"Token不能为空"}，
   被存成 .jpg 后，ddddocr 报的是 "cannot identify image file"，
   错误信息完全指不到真正的原因（Token 失效）。

2. **识别结果长度不等于 4 就判定失败**，需要重新下载再识别。
   验证码固定 4 位，长度不对基本就是识别错了（多认/少认一个字）。
"""
from __future__ import annotations

import pytest

from funeng_sync.login_test import (
    CAPTCHA_LENGTH,
    CaptchaError,
    _describe_bad_content,
    _is_image,
    is_valid,
)

# 极小的合法图片字节头（各自的前几个字节即可）
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00"
PNG = b"\x89PNG\r\n\x1a\n"
GIF = b"GIF89a"
BMP = b"BM\x00\x00"
WEBP = b"RIFF\x00\x00\x00\x00WEBP"

# 真实踩过的错误响应
TOKEN_ERROR = (
    b'{"code":20000,"message":"Token'
    b"\xe4\xb8\x8d\xe8\x83\xbd\xe4\xb8\xba\xe7\xa9\xba"
    b'"}'
)


class TestIsImage:
    """图片魔数判断。"""

    @pytest.mark.parametrize("data", [JPEG, PNG, GIF, BMP, WEBP])
    def test_real_images_pass(self, data: bytes) -> None:
        assert _is_image(data) is True

    def test_json_error_rejected(self) -> None:
        """接口的 JSON 错误响应不能被当成图片。"""
        assert _is_image(TOKEN_ERROR) is False

    def test_empty_rejected(self) -> None:
        assert _is_image(b"") is False

    def test_plain_text_rejected(self) -> None:
        assert _is_image(b"hello world") is False


class TestDescribeBadContent:
    """非图片内容的错误描述。"""

    def test_contains_server_message(self) -> None:
        """要把服务端给的错误信息带出来，否则没法排查。"""
        desc = _describe_bad_content(TOKEN_ERROR)
        assert "Token" in desc
        assert "不是图片" in desc

    def test_empty_content_handled(self) -> None:
        desc = _describe_bad_content(b"")
        assert desc  # 不抛异常，返回可读描述

    def test_long_content_truncated(self) -> None:
        """超长内容要截断，避免刷屏。"""
        desc = _describe_bad_content(b"x" * 5000)
        assert len(desc) < 500


class TestIsValid:
    """识别结果的长度校验。"""

    def test_correct_length_valid(self) -> None:
        assert is_valid("ab12") is True

    def test_too_short_invalid(self) -> None:
        assert is_valid("ab1") is False

    def test_too_long_invalid(self) -> None:
        assert is_valid("ab123") is False

    def test_empty_invalid(self) -> None:
        assert is_valid("") is False

    def test_default_length_is_four(self) -> None:
        """验证码固定 4 位——README 里 ddddocr 实测也是稳定输出 4 位。"""
        assert CAPTCHA_LENGTH == 4
        assert is_valid("abcd") is True
        assert is_valid("abc") is False


class TestCaptchaError:
    """自定义异常：业务层用它表达「这次识别/下载失败了」。"""

    def test_is_runtime_error(self) -> None:
        """继承 RuntimeError，方便调用方用 except RuntimeError 兜底。"""
        assert issubclass(CaptchaError, RuntimeError)
