"""HTTP 相关 —— 对应 index.js 的 downloadImage / postAliyun / getData 的请求部分。

全部用 requests 实现（对标 axios / fetch）。本文件只负责"发请求 + 解析"，
不持有 token 等状态，状态由 sync.FunengSync 管理。
"""
import base64
import logging
import time

import requests

from .config import (
    BAIDU_API_KEY,
    BAIDU_OCR_ENDPOINT,
    BAIDU_SECRET_KEY,
    HOST_URL,
    IMG_DIR,
    OCR_PROVIDER,
    PASSWORD_MD5,
    USER_ID,
    USER_NAME,
)
from .time_utils import end_of_day_millis, now_millis, yesterday_start_millis

logger = logging.getLogger("funeng_sync")

# 百度 access_token 缓存（有效期 30 天，缓存 25 天避免频繁换取浪费配额）
_baidu_token: str | None = None
_baidu_token_ts: float = 0.0
_BAIDU_TOKEN_TTL = 25 * 24 * 3600

# 百度错误码 -> 可操作的中文提示（只列常见几种，其余原样打印）
_BAIDU_ERROR_HINTS = {
    4: "并发/QPS 超限，降低调用频率后重试",
    6: (
        "应用无该接口权限。请到百度智能云「文字识别 OCR」控制台 → 应用列表，"
        "确认应用已勾选「通用文字识别」，并改用该应用的 API Key / Secret Key"
        "（其他产品如「图像识别」「千帆」的 AK/SK 不通用，也需先在概览页领取免费额度）"
    ),
    17: "当日免费额度已用完，请到控制台领取/购买资源包",
    18: "已达 QPS 上限",
    110: "access_token 无效，检查 AK/SK 是否写错",
    111: "access_token 已过期（会自动刷新重试）",
    216015: "图片 base64 数据不合法",
    282810: "图片格式或大小不合法（支持 jpg/png/bmp，<4M）",
}


def _baidu_ocr_url(token: str) -> str:
    """按配置的接口名拼 OCR 地址（general_basic / accurate_basic 等）。"""
    return (
        f"https://aip.baidubce.com/rest/2.0/ocr/v1/{BAIDU_OCR_ENDPOINT}"
        f"?access_token={token}"
    )


def download_image(
    session: requests.Session, attempt: int = 1
) -> tuple[str | None, int]:
    """对应 downloadImage：下载验证码图片并落盘。

    ⚠️ 必须用共享 session 调用：服务器会把验证码会话 cookie 下发到 session，
    后续 try_login 用同一个 session 才能把 cookie 回传，否则必然"验证码错误"。

    返回 (本地路径, 时间戳)；时间戳与登录接口的 key 共用，必须一致。
    失败返回 (None, 0)。
    """
    date_time = now_millis()  # 对应 dateTime = dayjs().valueOf()
    image_url = f"{HOST_URL}/api/auth/verificationCode/captcha-image/{date_time}"
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    # 文件名带尝试次数，便于对照"第几次识别的是哪张图"
    local_path = IMG_DIR / f"attempt_{attempt}_{date_time}.jpg"
    try:
        resp = session.get(image_url, stream=True, timeout=10)
        resp.raise_for_status()
        with open(local_path, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        logger.info("🖼️ 验证码图片已保存 [第%d次] -> %s", attempt, local_path)
        return str(local_path), date_time
    except Exception as e:  # noqa: BLE001 - 与原 JS catch 行为一致
        logger.error("下载或保存图片时发生错误: %s", e)
        return None, 0


def get_baidu_token(force: bool = False) -> str | None:
    """用 AK/SK 换取百度 access_token（带缓存，避免频繁换取浪费配额）。

    返回 token 字符串；失败返回 None。force=True 时忽略缓存强制刷新，
    用于 token 失效后的重试。
    """
    global _baidu_token, _baidu_token_ts
    now = time.time()
    if not force and _baidu_token and (now - _baidu_token_ts) < _BAIDU_TOKEN_TTL:
        return _baidu_token

    url = "https://aip.baidubce.com/oauth/2.0/token"
    params = {
        "grant_type": "client_credentials",
        "client_id": BAIDU_API_KEY,
        "client_secret": BAIDU_SECRET_KEY,
    }
    try:
        resp = requests.post(url, params=params, timeout=10)
        data = resp.json()
        token = data.get("access_token")
        if token:
            _baidu_token, _baidu_token_ts = token, now
            return token
        logger.error("获取百度 access_token 失败: %s", data)
        return None
    except Exception as e:  # noqa: BLE001
        logger.error("获取百度 token 请求错误: %s", e)
        return None


def ocr_baidu(local_path: str) -> str | None:
    """对应 postAliyun：调百度通用文字识别 general_basic 识别验证码。

    返回 4 位码或 None。本地图片用 image 参数（base64，不含 data: URI 前缀）；
    百度返回 words_result 列表，拼接所有行并去空格后判断是否为 4 位验证码。
    token 失效（110/111）会自动刷新重试一次。
    """
    token = get_baidu_token()
    if not token:
        return None

    try:
        with open(local_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("ascii")
    except Exception as e:  # noqa: BLE001
        logger.error("读图失败: %s", e)
        return None

    url = _baidu_ocr_url(token)
    # 表单格式（x-www-form-urlencoded）；本地图片用 image 参数传 base64
    payload = {
        "image": image_b64,
        "detect_direction": "false",
        "detect_language": "false",
        "paragraph": "false",
        "probability": "false",
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }

    for attempt in range(2):  # 第 2 次循环仅在 token 失效时强制刷新后重试
        try:
            resp = requests.post(url, headers=headers, data=payload, timeout=15)
            resp.encoding = "utf-8"
            # 打印原始返回，识别失败时一眼看清是接口报错还是结果不对
            logger.info(
                "OCR 原始返回 status=%s body=%s", resp.status_code, resp.text[:500]
            )
            data = resp.json()
        except Exception as e:  # noqa: BLE001
            logger.error("百度 OCR 请求错误: %s", e)
            return None

        if data.get("error_code"):
            error_code = data.get("error_code")
            # 110/111 = token 无效或过期，强制刷新后重试一次
            if error_code in (110, 111) and attempt == 0:
                logger.warning("百度 token 失效，刷新后重试")
                token = get_baidu_token(force=True)
                if not token:
                    return None
                url = _baidu_ocr_url(token)
                continue
            hint = _BAIDU_ERROR_HINTS.get(error_code)
            logger.warning(
                "❌ 百度 OCR 返回错误: %s %s%s",
                error_code,
                data.get("error_msg"),
                f"  → {hint}" if hint else "",
            )
            return None

        words_result = data.get("words_result") or []
        # 拼接所有识别行，去掉空格后判断是否为 4 位验证码
        text = "".join(w.get("words", "") for w in words_result).replace(" ", "")
        logger.info("百度识别文本: %r (图片 %s)", text, local_path)
        if len(text) == 4:
            logger.info("✅ 识别成功 [图片 %s] -> 验证码 %s", local_path, text)
            return text
        logger.warning("⚠️ 识别结果非 4 位 [图片 %s] text=%s", local_path, text)
        return None
    return None


# ---------------- 本地离线识别（备选方案，不依赖百度云）----------------
_ddddocr_instance = None


def _get_ddddocr():
    """懒加载 ddddocr（首次会加载模型，约 1~2 秒）；未安装时返回 None。"""
    global _ddddocr_instance
    if _ddddocr_instance is None:
        try:
            import ddddocr  # 可选依赖

            _ddddocr_instance = ddddocr.DdddOcr(show_ad=False)
        except Exception as e:  # noqa: BLE001
            logger.error("本地识别不可用，请先 pip install ddddocr（原因: %s）", e)
            return None
    return _ddddocr_instance


def ocr_ddddocr(local_path: str) -> str | None:
    """用 ddddocr 在本地识别验证码：无需 AK/SK、无需联网，专为验证码训练。"""
    ocr = _get_ddddocr()
    if ocr is None:
        return None
    try:
        with open(local_path, "rb") as f:
            image_bytes = f.read()
        text = (ocr.classification(image_bytes) or "").replace(" ", "")
    except Exception as e:  # noqa: BLE001
        logger.error("本地识别出错: %s", e)
        return None

    logger.info("本地识别文本: %r (图片 %s)", text, local_path)
    if len(text) == 4:
        logger.info("✅ 识别成功 [图片 %s] -> 验证码 %s", local_path, text)
        return text
    logger.warning("⚠️ 识别结果非 4 位 [图片 %s] text=%s", local_path, text)
    return None


def ocr_captcha(local_path: str) -> str | None:
    """验证码识别统一入口：按 config.OCR_PROVIDER 分发（baidu / ddddocr）。"""
    if OCR_PROVIDER == "ddddocr":
        return ocr_ddddocr(local_path)
    return ocr_baidu(local_path)


def try_login(
    session: requests.Session, code: str, date_time: int
) -> tuple[str, str | None]:
    """对应登录 POST。必须用同一个 session 调用以回传验证码 cookie。

    返回 ("ok", token) / ("captcha_error", None) / ("server_error", None)。
    """
    url = f"{HOST_URL}/api/auth/jwt/token"
    payload = {
        "key": date_time,
        "loginName": USER_NAME,
        "password": PASSWORD_MD5,
        "verificationCode": code,
    }
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "Accept": "application/json, text/plain, */*",
    }
    try:
        # 用 session.post：自动带回下载验证码时拿到的会话 cookie
        resp = session.post(url, json=payload, headers=headers, timeout=10)
        data = resp.json()
        logger.info("登录接口返回: %s", data)
    except Exception as e:  # noqa: BLE001
        logger.error("登录请求错误: %s", e)
        return "server_error", None

    if not data.get("code") and data.get("data", {}).get("token"):
        return "ok", data["data"]["token"]
    if data.get("code") == -1 and data.get("message") == "验证码错误":
        return "captcha_error", None
    logger.error("登录接口异常返回: %s", data)
    return "server_error", None


def build_payload(device_code: str, read_time_raw: str, total_flux) -> list:
    """对应 getData 里构造的 obj / payload（纯函数，便于单测）。

    obj = {"deviceCode": ...}
    obj[f"T_{readTime}"] = {"datas": {"internetTraffic": totalFlux}}
    payload = [obj]
    """
    obj: dict = {"deviceCode": device_code}
    obj[f"T_{read_time_raw}"] = {"datas": {"internetTraffic": total_flux}}
    return [obj]


def fetch_meter_data(
    session: requests.Session, fm_address: str, meter_id: str, token: str
) -> dict | None:
    """对应 getData 的请求部分：拉取水表实时数据表，返回解析后的 json 或 None。"""
    start = yesterday_start_millis()  # dayjs().subtract(1,'day').startOf('day')
    end = end_of_day_millis()         # dayjs().endOf('day')
    params = {
        "startDate": str(start),
        "endDate": str(end),
        "fmAddress": fm_address,
        "meterId": meter_id,
    }
    url = f"{HOST_URL}/api/largeCustomer/operationManagement/meterRealTimeDataTable"
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "Accept": "application/json, text/plain, */*",
        "Tw-Authorization": token,
        "Cookie": f"userId={USER_ID}; userName={USER_NAME}; Tw-Authorization={token};",
    }
    try:
        resp = session.get(url, params=params, headers=headers, timeout=15)
        return resp.json()
    except Exception as e:  # noqa: BLE001
        logger.error("请求错误: %s", e)
        return None
