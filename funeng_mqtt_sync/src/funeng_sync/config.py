"""全局配置：验证码下载地址、本地图片目录、网络超时等常量。"""
from __future__ import annotations

from pathlib import Path

# 项目根目录（src/funeng_sync/config.py 往上三级即 funeng_mqtt_sync/）
ROOT = Path(__file__).resolve().parents[2]

# 验证码图片地址（只放稳定端点，不带 ?t= 缓存戳）：
# t 由 download_captcha() 每次请求时用当前时间戳动态生成。
# 写死 t 会导致每次下载都是同一个 URL——既可能被代理缓存反复返回
# 同一张（过期）验证码，旧时间戳也可能被服务端判定为失效。
#VERIFY_CODE_URL = "http://www.zghaohua.com:100/VerifyCode"

#VERIFY_CODE_URL = "https://admin-api.iemp.fox-energytec.com/authorization-server/no-auth/captcha/graphics?type=png&uuid=5bb9d279-79b4-443a-8273-b94be4b77555"
VERIFY_CODE_URL = "http://10.0.0.1:8080/api/auth/verificationCode/captcha-image/"

# 验证码下载后保存到本地的目录
IMG_DIR = ROOT / "img"

# 下载验证码的超时时间（秒）
HTTP_TIMEOUT = 10
