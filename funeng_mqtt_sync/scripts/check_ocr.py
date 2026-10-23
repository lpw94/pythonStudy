"""OCR 自检脚本 —— 不登录、不连 MQTT，只验证「验证码识别」这一环。

用法（用 3.12 环境，ddddocr 依赖 opencv）：
    .py312/python.exe scripts/check_ocr.py            # 用 img/ 里最新一张图
    .py312/python.exe scripts/check_ocr.py 图片路径    # 指定图片

早前这个脚本依赖已裁剪掉的 `http_client.ocr_captcha` / `ocr_ddddocr`，
早就跑不起来了。现在直接复用 `login_test.recognize`（本地 ddddocr 实现）。
"""
import sys
from pathlib import Path

from funeng_sync.login_test import CAPTCHA_LENGTH, CaptchaError, recognize

ROOT = Path(__file__).resolve().parent.parent


def latest_image() -> Path | None:
    """取 img/ 目录里最新的一张验证码图片。"""
    img_dir = ROOT / "img"
    if not img_dir.exists():
        return None
    jpgs = sorted(img_dir.glob("*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)
    return jpgs[0] if jpgs else None


def main() -> int:
    print("=" * 60)
    print("识别方案 = ddddocr（本地离线，无需联网 / AK-SK）")
    print("=" * 60)

    # 第 1 步：拿一张验证码图片
    img = Path(sys.argv[1]) if len(sys.argv) > 1 else latest_image()
    if img is None or not img.exists():
        print("❌ 没找到验证码图片。")
        print("   请先跑一次 -m funeng_sync.login 生成 img/*.jpg，或手动传图片路径。")
        return 1
    print(f"📷 使用图片：{img}")

    # 第 2 步：识别
    try:
        text = recognize(str(img))
    except CaptchaError as e:
        print(f"❌ 识别异常：{e}")
        return 2

    print("-" * 60)
    if len(text) == CAPTCHA_LENGTH:
        print(f"✅ 识别成功：{text}")
        print("   如果登录仍失败，问题不在识别环节——多半是 key 与验证码时间戳对不上。")
        return 0
    print(f"⚠️ 本次没识别出 {CAPTCHA_LENGTH} 位验证码（得到 {text!r}）。")
    print("   · 识别文本不是 4 位 → 验证码带干扰线，属正常波动，重试即可")
    print("   · 多次失败 → 可人工核对 img/ 下的历史样本")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
