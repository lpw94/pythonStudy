"""示例：把 requests / json / datetime / 文件 IO 四个常用库串成一个最小可运行流程。

流程：用 requests 下载验证码图片 -> 用 pathlib 写盘 -> 用 datetime 生成毫秒时间戳
      -> 用 json 把"识别结果"写出再读回验证。

网络不可达时自动降级（不抛异常），其余流程照常演示，方便离线学习。

运行（用 3.12 环境）：
    E:/workBuddy/pythonStudy/.py312/python.exe -m funeng_sync.demo_stdlib
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import requests

# 0. 配置（仅示例；真实值在 funeng_sync/config.py）
HOST = "http://10.0.0.1:8080"
CAPTCHA_URL = f"{HOST}/api/auth/verificationCode/captcha-image/{{ts}}"
# 图片目录定位到项目根的 img/：__file__ 在 src/funeng_sync/ 下，上溯三级即项目根
IMG_DIR = Path(__file__).resolve().parent.parent.parent / "img"


def now_ms() -> int:
    """① datetime：生成 UTC 毫秒时间戳（常用于验证码防缓存戳）。"""
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def fetch_captcha(session: requests.Session, ts_ms: int) -> bytes | None:
    """② requests：用同一个 Session 下载验证码图片。

    离线 / 失败返回 None（演示性质，不中断后续流程）。
    """
    try:
        url = CAPTCHA_URL.format(ts=ts_ms)
        resp = session.get(url, timeout=10)
        resp.raise_for_status()
        return resp.content
    except Exception as exc:  # noqa: BLE001 - 演示用：降级而非崩溃
        print(f"[requests] 下载失败（离线演示跳过）: {exc}")
        return None


def save_bytes(data: bytes, name: str) -> Path:
    """③ 文件 IO（pathlib）：写二进制文件，自动建目录。"""
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    path = IMG_DIR / name
    path.write_bytes(data)
    return path


def dump_json(obj: dict, path: Path) -> None:
    """④ json：对象 -> 文件（中文原样 + 缩进 2 空格）。"""
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path: Path) -> dict:
    """④ json：文件 -> 对象。"""
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    session = requests.Session()

    ts = now_ms()  # ①
    print(f"[datetime] 毫秒时间戳 = {ts}")

    img = fetch_captcha(session, ts)  # ②
    if img:
        path = save_bytes(img, f"demo_{ts}.jpg")  # ③
        print(f"[pathlib] 图片已保存: {path}")
    else:
        path = save_bytes(b"", f"demo_{ts}.jpg")  # ③ 离线占位
        print(f"[pathlib] 离线占位文件: {path}")

    # ④ json：把"模拟识别结果"写出再读回
    result = {"ts": ts, "code": "Zybq", "ok": True}
    json_path = IMG_DIR / f"demo_{ts}.json"
    dump_json(result, json_path)  # ③④
    print(f"[json] 已写出: {json_path}")

    back = load_json(json_path)  # ④
    print(f"[json] 读回: {back}")


if __name__ == "__main__":
    main()
