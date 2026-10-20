"""下载配置里的验证码图片到本地，再用 ddddocr 本地识别并打印结果。

流程：config.VERIFY_CODE_URL 下载图片 -> 存到 img/ -> ddddocr 识别 -> 打印结果。
下载后会保留最近 keep 张图片（默认 10），更早的自动清理，方便人工批量对照。

运行（用 3.12 环境）：
    E:/workBuddy/pythonStudy/.py312/python.exe -m funeng_sync.captcha_demo
    E:/workBuddy/pythonStudy/.py312/python.exe -m funeng_sync.captcha_demo img/xxx.jpg
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import requests

from funeng_sync import config

# ddddocr 模型只加载一次（约 1~2 秒），后续复用
_ocr = None

# 清理旧验证码时只删这些图片后缀，避免误删目录里其他文件
_IMG_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".bmp"}


def _get_ocr():
    global _ocr
    if _ocr is None:
        import ddddocr

        _ocr = ddddocr.DdddOcr(show_ad=False)
    return _ocr


def download_captcha(
    url: str | None = None, save_dir: str | Path | None = None, keep: int = 10
) -> Path:
    """把配置里的验证码图片下载到本地，返回保存路径。

    keep：保留最近多少张（按修改时间），更早的会自动清理，避免目录无限膨胀，
    同时保留近期的若干张供人工批量对照。设为 0 表示不清理。
    """
    url = url or config.VERIFY_CODE_URL
    save_dir = Path(save_dir or config.IMG_DIR)
    save_dir.mkdir(parents=True, exist_ok=True)

    # ?t= 是缓存戳：URL 没带查询参数时补一个当前时间戳，
    # 保证每次下载都是新验证码，同时绕过浏览器/代理缓存；
    # 调用方显式传了带参数的 URL 则尊重原样使用
    if "?" not in url:
        url = f"{url}?t={time.time()}"

    resp = requests.get(url, timeout=config.HTTP_TIMEOUT)
    resp.raise_for_status()
    if not resp.content:
        raise RuntimeError(f"下载到的内容为空：{url}")

    path = save_dir / f"captcha_{int(time.time() * 1000)}.jpg"
    path.write_bytes(resp.content)

    # 清理：只保留最近 keep 张（按修改时间倒序），更早的删除。
    # 放在保存成功之后，避免下载失败把旧图也误删；
    # 这样既能防止 img/ 无限膨胀，又能留下近期若干张供人工批量对照。
    if keep > 0:
        imgs = sorted(
            (p for p in save_dir.iterdir()
             if p.is_file() and p.suffix.lower() in _IMG_SUFFIXES),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for old in imgs[keep:]:
            old.unlink(missing_ok=True)

    return path


def recognize(image_path: str) -> str:
    """用 ddddocr 本地离线识别图片，返回识别文字（已去空格）。无需联网 / 密钥。"""
    ocr = _get_ocr()
    with open(image_path, "rb") as f:
        text = (ocr.classification(f.read()) or "").replace(" ", "")
    return text


def main() -> None:
    args = sys.argv[1:]
    if args:
        # 识别指定的本地图片（跳过下载）
        for p in args:
            print(f"{p} -> {recognize(p)}")
    else:
        # 不传参数：从配置的地址下载验证码到本地，再识别
        img = download_captcha()
        print(f"已下载：{img}")
        print(f"识别结果 -> {recognize(str(img))}")


if __name__ == "__main__":
    main()
