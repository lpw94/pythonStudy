"""编排层 —— 对应 index.js 的 handleLogin / getData / delayedLog / setInterval 主循环。

原 JS 用大量全局变量 + setTimeout 链，这里收敛成一个持有状态的 FunengSync 类，
但完整保留：登录锁、5 次上限、各分支重试时长、整点过滤、错峰取数、8 小时主循环。
"""
import logging
import threading
import time

import requests

from .config import (
    DELAY_BETWEEN_DEVICES_SECONDS,
    FIRST_DELAY_SECONDS,
    IMG_DIR,
    KEEP_CAPTCHA_IMAGES,
    LOOP_INTERVAL_MINUTES,
    MAX_LOGIN_ATTEMPTS,
    OPTION_LIST,
    PAUSE_AFTER_MAX_SECONDS,
    RETRY_CAPTCHA_ERROR_SECONDS,
    RETRY_NO_CODE_SECONDS,
    RETRY_NO_IMAGE_SECONDS,
    RETRY_SERVER_ERROR_SECONDS,
    RETRY_TOKEN_INVALID_SECONDS,
)
from .http_client import download_image, fetch_meter_data, ocr_captcha, try_login
from .mqtt_client import create_client, publish
from .time_utils import format_read_time, is_top_of_hour

logger = logging.getLogger("funeng_sync")

# 部分接口会拒绝 python-requests 默认 UA，统一带浏览器 UA 更稳
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class FunengSync:
    def __init__(self) -> None:
        self.token = ""
        self.login_attempts = 0
        self.is_logging_in = False
        self.date_time = 0  # 验证码时间戳，登录 key 共用
        self.client = create_client()
        # 共享 session：复验证码图片下发的会话 cookie，登录才能通过校验
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": _BROWSER_UA})

    # ---------------- 登录流程（对应 handleLogin）----------------
    def handle_login(self) -> None:
        # 用 while 循环替代原 JS 的 setTimeout 递归，避免深层递归且语义一致
        while True:
            if self.is_logging_in:
                logger.info("正在登录中，跳过重复调用")
                return
            if self.login_attempts >= MAX_LOGIN_ATTEMPTS:
                logger.info(
                    "登录失败次数已达上限 (%d次)，暂停2小时后重试", MAX_LOGIN_ATTEMPTS
                )
                time.sleep(PAUSE_AFTER_MAX_SECONDS)
                self.login_attempts = 0
                self.is_logging_in = False
                continue

            self.is_logging_in = True
            self.login_attempts += 1
            logger.info("开始第 %d 次登录尝试", self.login_attempts)

            # 不再每轮全删图片：只保留最近 N 张，便于排查"识别失败"是哪张图
            self._prune_images()

            img_src, ts = download_image(self.session, self.login_attempts)
            if not img_src:
                self.is_logging_in = False
                time.sleep(RETRY_NO_IMAGE_SECONDS)
                continue
            self.date_time = ts
            logger.info("📷 本次识别图片路径: %s （可打开查看验证码）", img_src)

            code = ocr_captcha(img_src)
            if not code:
                self.is_logging_in = False
                time.sleep(RETRY_NO_CODE_SECONDS)
                continue

            status, token = try_login(self.session, code, self.date_time)
            if status == "ok":
                self.token = token
                self.login_attempts = 0
                self.is_logging_in = False
                logger.info("获取token成功 %s", token)
                time.sleep(2)
                self.fetch_all()
                return
            if status == "captcha_error":
                self.is_logging_in = False
                time.sleep(RETRY_CAPTCHA_ERROR_SECONDS)
                continue
            # server_error
            self.is_logging_in = False
            time.sleep(RETRY_SERVER_ERROR_SECONDS)
            continue

    def _prune_images(self) -> None:
        """保留最近 KEEP_CAPTCHA_IMAGES 张验证码图片，删除更旧的（不再每轮全删）。"""
        if not IMG_DIR.exists():
            return
        jpgs = sorted(
            IMG_DIR.glob("*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True
        )
        for old in jpgs[KEEP_CAPTCHA_IMAGES:]:
            try:
                old.unlink()
                logger.debug("清理旧图片: %s", old.name)
            except Exception:  # noqa: BLE001
                pass

    # ---------------- 取数 + 发布（对应 getData / delayedLog）----------------
    def fetch_all(self) -> None:
        for index, dev in enumerate(OPTION_LIST):
            time.sleep(index * DELAY_BETWEEN_DEVICES_SECONDS)
            self.get_data(dev["fmAddress"], dev["meterId"], dev["deviceCode"])

    def get_data(self, fm_address: str, meter_id: str, device_code: str) -> None:
        logger.info("%s %s %s", fm_address, meter_id, device_code)
        data = fetch_meter_data(self.session, fm_address, meter_id, self.token)
        if data is None:
            return

        if data.get("code"):
            logger.info("获取数据错误，token失效！！重新登录")
            threading.Thread(target=self._retry_login, daemon=True).start()
            return

        table = (data.get("data") or {}).get("table") or []
        table_data = table[:33]  # 对应 [...data.data.table].slice(0, 33)
        if len(table_data) == 0:
            logger.info("今日数据不存在，自动发送0数据")
            return

        for row in table_data:
            if is_top_of_hour(row.get("readTime")):
                total_flux = row.get("totalFlux")
                read_time_raw = row.get("readTime")
                publish(self.client, device_code, read_time_raw, total_flux)
                logger.info(
                    "%s发送成功, 设备编号%s,流量 %s",
                    format_read_time(read_time_raw),
                    device_code,
                    total_flux,
                )

    def _retry_login(self) -> None:
        time.sleep(RETRY_TOKEN_INVALID_SECONDS)
        self.handle_login()

    # ---------------- 主循环（对应 setInterval 倒计时）----------------
    def run(self) -> None:
        second = FIRST_DELAY_SECONDS
        interval = LOOP_INTERVAL_MINUTES * 60
        while True:
            time.sleep(1)
            second -= 1
            if second == 0:
                logger.info("获取数据中...")
                # 登录放在线程里，避免阻塞倒计时循环（原 JS 的回调也是非阻塞的）
                threading.Thread(target=self.handle_login, daemon=True).start()
                second = interval
                
                #logger.info("倒计时 %d 秒...再次登录获取数据", second)
