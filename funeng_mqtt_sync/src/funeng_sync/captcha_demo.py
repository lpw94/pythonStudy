"""下载验证码 + ddddocr 离线识别（兼容入口）。

实现已统一到 `login_test.py`（含「识别长度不对就重新下载」的逻辑），
本模块只做转发，避免两份几乎相同的代码各自漂移。

运行（用 3.12 环境）：
    E:/workBuddy/pythonStudy/.py312/python.exe -m funeng_sync.captcha_demo
    E:/workBuddy/pythonStudy/.py312/python.exe -m funeng_sync.captcha_demo img/xxx.jpg
"""
from __future__ import annotations

from .login_test import (
    CAPTCHA_LENGTH,
    MAX_RETRY,
    CaptchaError,
    download_and_recognize,
    download_captcha,
    is_valid,
    recognize,
)

__all__ = [
    "CAPTCHA_LENGTH",
    "MAX_RETRY",
    "CaptchaError",
    "download_and_recognize",
    "download_captcha",
    "is_valid",
    "recognize",
    "main",
]


def main() -> None:
    """不带参数时走「下载 + 识别 + 失败重试」，带参数时只识别指定图片。"""
    import sys

    args = sys.argv[1:]
    if args:
        for p in args:
            print(f"{p} -> {recognize(p)}")
    else:
        img, text = download_and_recognize()
        print(f"已下载：{img}")
        print(f"识别结果 -> {text}")


if __name__ == "__main__":
    main()
