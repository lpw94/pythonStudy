"""极简识别：用 ddddocr 本地识别一张验证码图片并打印结果。

只保留「识别」这一个功能——无下载、无登录、无任何配置：
- 命令行传入图片路径：python -m funeng_sync.captcha_demo 图片路径
- 不传参数：识别 img/ 目录下所有 .jpg（方便人工对照判断）

运行（用 3.12 环境）：
    E:/workBuddy/pythonStudy/.py312/python.exe -m funeng_sync.captcha_demo
    E:/workBuddy/pythonStudy/.py312/python.exe -m funeng_sync.captcha_demo img/xxx.jpg
"""
from __future__ import annotations

import sys
from pathlib import Path


# ddddocr 模型只加载一次（约 1~2 秒），后续复用
_ocr = None


def _get_ocr():
    global _ocr
    if _ocr is None:
        import ddddocr

        _ocr = ddddocr.DdddOcr(show_ad=False)
    return _ocr


def recognize(image_path: str) -> str:
    """用 ddddocr 本地离线识别图片，返回识别文字（已去空格）。无需联网 / 密钥。"""
    ocr = _get_ocr()
    with open(image_path, "rb") as f:
        text = (ocr.classification(f.read()) or "").replace(" ", "")
    return text


def main() -> None:
    args = sys.argv[1:]
    if args:
        # 识别指定的图片
        for p in args:
            print(f"{p} -> {recognize(p)}")
    else:
        # 不传参数：识别 img/ 下所有 jpg
        images = sorted(Path("img").glob("*.jpg"))
        if not images:
            print("img/ 目录下没有 .jpg 文件，请先放一张验证码图片，或传入图片路径")
            return
        for img in images:
            print(f"{img} -> {recognize(str(img))}")


if __name__ == "__main__":
    main()
