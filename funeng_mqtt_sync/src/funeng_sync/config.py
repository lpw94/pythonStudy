"""全局配置：服务地址、账号、超时等常量。

敏感值（密码 md5）从项目根目录的 .env 读取，**不写死在本文件里**，
避免随 git 仓库一起外传（.env 已在 .gitignore 中）。

读取优先级：系统环境变量 > 项目根 .env > 本文件里的默认值。
"""
from __future__ import annotations

import os
from pathlib import Path

# 项目根目录（src/funeng_sync/config.py 往上三级即 funeng_mqtt_sync/）
ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv(path: Path) -> dict[str, str]:
    """读取 .env 文件。

    只支持 KEY=VALUE 和 # 注释两种语法，不引 python-dotenv（这个项目
    坚持「标准库能解决就不加依赖」）。已存在的系统环境变量优先级更高。

    Args:
        path: .env 文件路径。

    Returns:
        键值对字典；文件不存在时返回空字典。
    """
    env: dict[str, str] = {}
    if not path.is_file():
        return env

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


_ENV = _load_dotenv(ROOT / ".env")


def _get(key: str, default: str = "") -> str:
    """取配置值：系统环境变量优先于 .env，其次用默认值。"""
    return os.environ.get(key) or _ENV.get(key, default)


# ---------------------------------------------------------------- 网络

# 富能平台服务端（内网直连地址）
HOST_URL = _get("FUNENG_HOST_URL", "http://10.0.0.1:8080")

# 登录接口：拿验证码 + 密码换 JWT token
LOGIN_URL = f"{HOST_URL}/api/auth/jwt/token"

# 验证码图片接口。**时间戳是拼在路径段上的**，见 login_test.build_captcha_url。
VERIFY_CODE_URL = f"{HOST_URL}/api/auth/verificationCode/captcha-image"

# 走企业代理会导致内网地址下载到 0 字节 / 44 字节的 JSON 错误，默认绕过。
# 确实需要走代理的场景（比如访问外网域名）再改成 "1"。
BYPASS_ENV_PROXY = _get("FUNENG_BYPASS_ENV_PROXY", "1") not in ("0", "false", "False")

# 下载验证码的超时时间（秒）
HTTP_TIMEOUT = int(_get("FUNENG_HTTP_TIMEOUT", "10"))

# ---------------------------------------------------------------- 账号

# 登录账号
USER_NAME = _get("FUNENG_USER_NAME", "your_account")

# 登录密码的 md5 —— 敏感值，只从 .env / 环境变量读，不进版本库。
# 为空时 login 模块会在真正发请求前抛错，不会带着空密码去打扰服务端。
PASSWORD_MD5 = _get("FUNENG_PASSWORD_MD5")

# ---------------------------------------------------------------- 本地目录

# 验证码下载后保存到本地的目录
IMG_DIR = ROOT / "img"
