"""配置常量 —— 对应 index.js 顶部的全局变量。

含 hostUrl / topic / options / optionList 等非敏感配置。

⚠️ 敏感凭据不写死在代码里：登录密码（md5）与百度 OCR 的 AK/SK 改为从环境变量读取
（见 .env.example）。运行时会在项目根目录找 `.env` 并自动载入（不依赖第三方库）。
这样 `config.py` 可以安全地提交进 git，真实凭据只存在于本地 `.env`（已被 git 忽略）。
"""
import os
from pathlib import Path

# 轻量 .env 载入：项目根目录的 .env（无需 python-dotenv 依赖）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


def _load_dotenv() -> None:
    """读取项目根目录的 .env 到 os.environ（仅填充尚未存在的键）。"""
    if not _ENV_FILE.exists():
        return
    for raw in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()

# 业务接口地址（对应 hostUrl）
HOST_URL = "http://10.0.0.1:8080"

# MQTT 上报主题（对应 topic）
TOPIC = "third-party/XTZXYYSBY001/v2/up/report"

# MQTT 连接参数（对应 use_mqtt.js 的 connectOptions + 原 options）
MQTT = {
    "host": "121.37.27.139",        # 生产环境代理（use_mqtt.js）
    "port": 1883,
    "client_id": "mqttx_011c6c1e",
    "username": "thinker",
    "password": "123456",
}

# 登录账号（对应 userName / userId）
USER_NAME = "your_account"
USER_ID = "1990"

# 登录密码（已是 md5，对应 login 接口的 password 字段）—— 从环境变量读取，不入库
PASSWORD_MD5 = os.environ.get("FUNENG_PASSWORD_MD5", "")
if not PASSWORD_MD5:
    raise RuntimeError(
        "缺少环境变量 FUNENG_PASSWORD_MD5：请复制 .env.example 为 .env 并填入真实值"
    )

# 百度 OCR（替代原阿里云 OCR）：通用文字识别
# 用 AK/SK 换取 access_token，本地图片走 image 参数（base64，不含 data URI 前缀）
#
# ⚠️ AK/SK 必须来自「文字识别 OCR」这个产品的应用，且该应用要勾选「通用文字识别」；
#    跨产品（图像识别 / 千帆大模型 / 语音技术…）的 AK/SK 不通用，用错会返回
#    error_code=6 No permission to access data。
BAIDU_API_KEY = os.environ.get("BAIDU_API_KEY", "")
BAIDU_SECRET_KEY = os.environ.get("BAIDU_SECRET_KEY", "")
if not BAIDU_API_KEY or not BAIDU_SECRET_KEY:
    raise RuntimeError(
        "缺少环境变量 BAIDU_API_KEY / BAIDU_SECRET_KEY："
        "请复制 .env.example 为 .env 并填入真实值"
    )

# 选择调用的 OCR 接口：
#   general_basic  通用文字识别（标准版，QPS/额度更宽）
#   accurate_basic 通用文字识别（高精度版，验证码这类小图识别率通常更好）
BAIDU_OCR_ENDPOINT = "general_basic"

# 验证码识别方案：
#   ddddocr  本地离线识别（专为验证码训练，无需 AK/SK，需 pip install ddddocr）← 默认
#   baidu    走百度云 OCR（需要联网 + 应用已开通接口），保留作为在线兜底
OCR_PROVIDER = "ddddocr"

# 设备列表（对应 optionList: fmAddress / meterId / deviceCode）
OPTION_LIST = [
    {"fmAddress": "2111222166", "meterId": "922343", "deviceCode": "XT200025"},
    {"fmAddress": "2009210933", "meterId": "139", "deviceCode": "XT200026"},
    {"fmAddress": "2111222161", "meterId": "922333", "deviceCode": "XT200028"},
    {"fmAddress": "22020103208", "meterId": "1282833", "deviceCode": "XT220498"},
    {"fmAddress": "122306208584", "meterId": "28054770476", "deviceCode": "XT294506"},
]

# 登录重试策略（对应 MAX_LOGIN_ATTEMPTS 与各 setTimeout 时间）
MAX_LOGIN_ATTEMPTS = 5
PAUSE_AFTER_MAX_SECONDS = 2 * 60 * 60   # 5 次全失败，暂停 2 小时
RETRY_NO_IMAGE_SECONDS = 5              # 取验证码图片失败
RETRY_NO_CODE_SECONDS = 5               # 验证码识别失败
RETRY_CAPTCHA_ERROR_SECONDS = 10        # 验证码错误（接口返回 -1）
RETRY_SERVER_ERROR_SECONDS = 60 * 60    # 接口 500 等异常
RETRY_TOKEN_INVALID_SECONDS = 3         # 取数返回 token 失效
DELAY_BETWEEN_DEVICES_SECONDS = 2       # delayedLog 错峰：index * 2s

# 主循环（对应 setInterval 倒计时逻辑）
FIRST_DELAY_SECONDS = 10                # 启动后首次登录等待
LOOP_INTERVAL_MINUTES = 480             # 之后每 480 分钟（8 小时）一次

# 验证码图片存放目录（对应 ./img）
IMG_DIR = Path("./img")

# 保留最近的验证码图片数量，便于排查"识别失败"问题（原 JS 每轮全删，导致看不到图）
KEEP_CAPTCHA_IMAGES = 20
