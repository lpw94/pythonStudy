"""OCR 自检脚本 —— 不登录、不连 MQTT，只验证"验证码识别"这一环。

用法：
    .venv/Scripts/python.exe scripts/check_ocr.py            # 用 img/ 里最新一张图
    .venv/Scripts/python.exe scripts/check_ocr.py 图片路径    # 指定图片

排查顺序：先看 AK/SK 能不能换到 token，再看 OCR 接口有没有权限。
输出里每个环节都会给出结论，照着改就行。
"""
import sys
from pathlib import Path

from funeng_sync import config
from funeng_sync.http_client import ocr_captcha, ocr_ddddocr

ROOT = Path(__file__).resolve().parent.parent


def latest_image() -> Path | None:
    img_dir = ROOT / "img"
    if not img_dir.exists():
        return None
    jpgs = sorted(img_dir.glob("*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)
    return jpgs[0] if jpgs else None


def main() -> int:
    print("=" * 60)
    print(f"识别方案 OCR_PROVIDER = {config.OCR_PROVIDER}")
    if config.OCR_PROVIDER == "baidu":
        print(f"接口     = {config.BAIDU_OCR_ENDPOINT}")
        key = config.BAIDU_API_KEY
        print(f"API_KEY  = {key[:8]}...（后 4 位 {key[-4:]}）")
    print("=" * 60)

    # 第 1 步：换取 access_token（只对百度方案有意义）
    if config.OCR_PROVIDER == "baidu":
        from funeng_sync.http_client import get_baidu_token

        token = get_baidu_token(force=True)
        if not token:
            print("❌ 换 token 失败：AK/SK 无效，或网络不通。")
            print("   检查 config 里的百度 AK/SK 是否与控制台一致。")
            return 1
        print(f"✅ 换 token 成功：{token[:12]}...（说明 AK/SK 本身有效）")

    # 第 2 步：拿一张验证码图片
    img = Path(sys.argv[1]) if len(sys.argv) > 1 else latest_image()
    if img is None or not img.exists():
        print("❌ 没找到验证码图片，请先跑一次主程序生成 img/*.jpg，或手动传图片路径。")
        return 1
    print(f"📷 使用图片：{img}")

    # 第 3 步：识别
    if config.OCR_PROVIDER == "ddddocr":
        text = ocr_ddddocr(str(img))
    else:
        text = ocr_captcha(str(img))

    print("-" * 60)
    if text:
        print(f"✅ 识别成功：{text}")
        print("   如果主程序仍登录失败，问题在验证码本身或 cookie 会话，不在识别环节。")
        return 0
    print("⚠️ 本次没识别出 4 位验证码。")
    print("   · error_code=6 → 应用无 OCR 权限，去「文字识别 OCR」控制台勾选接口")
    print("   · 识别文本不是 4 位 → 验证码带干扰线，可换 accurate_basic 或 ddddocr")
    print("   · 可多跑几次（验证码难度随机），或把 OCR_PROVIDER 改成 ddddocr 对比")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
