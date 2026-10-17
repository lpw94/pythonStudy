"""最小演示：下载验证码 → ddddocr 离线识别 → 调用登录接口（仅登录，不含取数 / MQTT）。

这是给 Python 学习用的「最小可跑通链路」：把 funeng 登录这条最核心的环节单独拎出来。
复用 http_client 里已经封装好的 download_image / ocr_ddddocr / try_login，
它们正确处理了「同一 requests.Session 回传验证码 cookie」这个关键点——
如果下载验证码和登录用了不同的 session，服务器就认为"验证码对不上"，必然返回"验证码错误"。

运行（在 funeng_mqtt_sync 目录下，用 3.12 环境，需先有 .env）：
    E:/workBuddy/pythonStudy/.py312/python.exe -m funeng_sync.simple_login
"""
from __future__ import annotations

import logging

import requests

from .config import PASSWORD_MD5, USER_ID, USER_NAME
from .http_client import download_image, ocr_ddddocr, try_login

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger("simple_login")


def run(max_attempts: int = 5) -> str | None:
    """只做登录这一件事，成功即可。

    ddddocr 对验证码偶有 ~1/4 的误读（比如把数字 5 认成字母 b），
    所以这里做最多 max_attempts 次重试，命中一次成功就返回 token。
    返回登录拿到的 token；全部失败返回 None。
    """
    # 关键：验证码图片下载时，服务器会把会话 cookie 下发到这个 session，
    # 登录必须用「同一个 session」发请求，才能把 cookie 回传回去。
    session = requests.Session()

    for attempt in range(1, max_attempts + 1):
        logger.info("===== 第 %d/%d 次尝试 =====", attempt, max_attempts)

        local_path, date_time = download_image(session, attempt)
        if not local_path:
            logger.warning("下载验证码失败，重试")
            continue

        code = ocr_ddddocr(local_path)
        if not code:
            logger.warning("识别失败（非 4 位），重试")
            continue

        status, token = try_login(session, code, date_time)
        if status == "ok":
            logger.info("登录成功！token=%s", token)
            return token

        logger.warning("本次未登录成功（status=%s），重试", status)

    logger.error("达到最大重试次数，登录失败")
    return None


if __name__ == "__main__":
    run()
