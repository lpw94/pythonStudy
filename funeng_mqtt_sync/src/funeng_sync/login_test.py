"""下载配置里的验证码图片到本地，再用 ddddocr 本地识别并打印结果。

流程：config.VERIFY_CODE_URL 下载图片 -> 存到 img/ -> ddddocr 识别 -> 打印结果。
下载后会保留最近 keep 张图片（默认 10），更早的自动清理，方便人工批量对照。

识别结果长度不等于 CAPTCHA_LENGTH 时（识别失败），会重新下载再识别，
最多重试 MAX_RETRY 次。

运行（用 3.12 环境）：
    E:/workBuddy/pythonStudy/.py312/python.exe -m funeng_sync.login_test
    E:/workBuddy/pythonStudy/.py312/python.exe -m funeng_sync.login_test img/xxx.jpg
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

# 验证码位数：识别结果不是这个长度就算识别失败
CAPTCHA_LENGTH = 4

# 识别失败后最多重新下载重试几次
MAX_RETRY = 5


class CaptchaError(RuntimeError):
    """验证码相关错误（下载到非图片内容、识别连续失败等）。"""


def _get_ocr():
    global _ocr
    if _ocr is None:
        import ddddocr

        _ocr = ddddocr.DdddOcr(show_ad=False)
    return _ocr


def _is_image(content: bytes) -> bool:
    """判断响应内容是不是图片。

    为什么要专门判：接口在缺少 Token 等情况下会返回 **JSON 错误**，
    比如 {"code":20000,"message":"Token不能为空"}——HTTP 状态码仍是 200。
    如果直接存成 .jpg，后面 ddddocr 识别时会抛
    "cannot identify image file"，报错信息完全指不到真正的原因。
    """
    if not content:
        return False
    # 图片魔数（file signature）：JPEG / PNG / GIF / BMP / WEBP
    return content.startswith(
        (b"\xff\xd8\xff", b"\x89PNG", b"GIF8", b"BM", b"RIFF")
    )


def _describe_bad_content(content: bytes) -> str:
    """非图片内容时，尽量把服务端的错误信息提取出来，便于排查。"""
    try:
        text = content.decode("utf-8", errors="replace").strip()
    except Exception:  # pragma: no cover - decode 几乎不会失败，兜底而已
        text = ""
    if not text:
        return f"内容不是图片（{len(content)} 字节）"
    # 只截前 200 字符，避免超长响应刷屏
    return f"内容不是图片（{len(content)} 字节）：{text[:200]}"


def download_captcha(
    url: str | None = None, save_dir: str | Path | None = None, keep: int = 10
) -> Path:
    """把配置里的验证码图片下载到本地，返回保存路径。

    keep：保留最近多少张（按修改时间），更早的会自动清理，避免目录无限膨胀，
    同时保留近期的若干张供人工批量对照。设为 0 表示不清理。

    Raises:
        CaptchaError: 服务端返回的不是图片（通常是 JSON 错误，如 Token 失效）。
    """
    url = url or config.VERIFY_CODE_URL
    save_dir = Path(save_dir or config.IMG_DIR)
    save_dir.mkdir(parents=True, exist_ok=True)

    # ?t= 是缓存戳：用毫秒级时间戳（如 1792755919367，即 JS 的 Date.now()），
    # 保证每次下载都是新验证码，同时绕过浏览器/代理缓存；
    # 调用方显式传了带参数的 URL 则尊重原样使用
    if "?" not in url:
        url = f"{url}{int(time.time() * 1000)}"

    print(f"下载验证码：{url} -> {save_dir}")
    resp = requests.get(url, timeout=config.HTTP_TIMEOUT)
    resp.raise_for_status()
    if not resp.content:
        raise CaptchaError(f"下载到的内容为空：{url}")

    # 关键：先确认是图片再落盘。否则服务端返回的 JSON 错误
    # （HTTP 200 + {"code":20000,"message":"Token不能为空"}）
    # 会被存成 .jpg，既污染目录，又让后续识别报一个指向不明的错。
    if not _is_image(resp.content):
        raise CaptchaError(_describe_bad_content(resp.content))

    # 用纳秒时间戳做文件名：登录重试时两次下载可能落在同一毫秒内，
    # 毫秒命名会互相覆盖，纳秒可将碰撞概率降到趋近于 0
    path = save_dir / f"captcha_{time.time_ns()}.jpg"
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
    """用 ddddocr 本地离线识别图片，返回识别文字（已去空格）。无需联网 / 密钥。

    识别失败（不是合法图片）时抛 CaptchaError，调用方可据此重试。
    """
    ocr = _get_ocr()
    with open(image_path, "rb") as f:
        data = f.read()
    try:
        text = (ocr.classification(data) or "").replace(" ", "")
    except Exception as e:
        raise CaptchaError(f"识别失败：{e}") from e
    return text


def is_valid(text: str, length: int = CAPTCHA_LENGTH) -> bool:
    """判断识别结果是否有效。

    只看长度：验证码固定 length 位，长度不对基本就是识别错了
    （多识别一个字符、少识别一个、或把干扰线识别成了字）。
    """
    return len(text) == length


def download_and_recognize(
    max_retry: int = MAX_RETRY,
    length: int = CAPTCHA_LENGTH,
    save_dir: str | Path | None = None,
) -> tuple[Path, str]:
    """下载验证码并识别，识别结果长度不对就重新下载再试。

    这是实际登录流程需要的语义：**必须拿到一个长度正确的验证码**才能提交登录。
    识别错了还用，会导致一次登录失败、还可能触发服务端的风控。

    Args:
        max_retry: 最多尝试几次（含首次）。1 表示不重试。
        length: 期望的验证码位数。
        save_dir: 图片保存目录，None 表示用配置里的。

    Returns:
        (图片路径, 识别结果) —— 结果长度保证等于 length。

    Raises:
        CaptchaError: 尝试次数用尽仍未识别出正确长度的验证码。
    """
    last_text = ""
    last_err: str = ""

    for attempt in range(1, max_retry + 1):
        try:
            img = download_captcha(save_dir=save_dir)
        except CaptchaError as e:
            # 下载失败（多半是 Token 过期这类服务端错误）也算一次尝试，
            # 但换一张图也解决不了——所以只重试不换 URL，等下一次循环重新取。
            last_err = str(e)
            print(f"[{attempt}/{max_retry}] 下载失败：{last_err}")
            if attempt < max_retry:
                time.sleep(1)
            continue

        try:
            text = recognize(str(img))
        except CaptchaError as e:
            last_err = str(e)
            print(f"[{attempt}/{max_retry}] 识别异常：{last_err}")
            if attempt < max_retry:
                time.sleep(1)
            continue

        last_text = text
        if is_valid(text, length):
            print(f"[{attempt}/{max_retry}] 识别成功：{text}  ({img})")
            return img, text

        print(
            f"[{attempt}/{max_retry}] 识别结果长度 {len(text)} != {length}，"
            f"判定为识别失败：{text!r}  重新下载再试"
        )
        if attempt < max_retry:
            time.sleep(1)

    raise CaptchaError(
        f"尝试 {max_retry} 次仍未识别出 {length} 位验证码。"
        f"最后一次结果：{last_text!r}；最后一次错误：{last_err or '无'}"
    )


def main() -> None:
    args = sys.argv[1:]
    if args:
        # 识别指定的本地图片（跳过下载）
        for p in args:
            print(f"{p} -> {recognize(p)}")
    else:
        # 不传参数：下载验证码到本地再识别，识别失败自动重试
        img, text = download_and_recognize()
        print(f"已下载：{img}")
        print(f"识别结果 -> {text}")


if __name__ == "__main__":
    main()
