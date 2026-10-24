"""全局配置：服务地址、账号、超时等常量。

敏感值全部从项目根目录的 .env 读取，**不写死在本文件里**，
避免随 git 仓库一起外传（.env 已在 .gitignore 中）。

读取优先级：系统环境变量 > 项目根 .env > 本文件里的默认值。

设计原则：**代码里不出现任何真实的生产地址与账号**。
- 生产环境地址、登录账号、密码 md5 都属于「知道了就能连上内网服务」的信息，
  公开仓库里出现等于送上门。
- 因此下面这些项**没有默认值**——缺失时由 require_*() 显式抛错，
  而不是悄悄用一个硬编码的值兜底（那正是泄露的源头）。
- 文档、注释、示例输出里一律用占位符（如 10.0.0.1 / your_account）。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

# 项目根目录（src/funeng_sync/config.py 往上三级即 funeng_mqtt_sync/）
ROOT = Path(__file__).resolve().parents[2]


class ConfigError(RuntimeError):
    """缺少必要的配置项（通常是 .env 没写或写漏了）。"""


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


def _require(key: str, value: str, hint: str) -> str:
    """配置项缺失时抛 ConfigError，并给出「去哪填」的明确指引。

    不提供兜底默认值是刻意的：宁可启动失败，也不要用一个写死的
    生产地址把秘密重新带回版本库。
    """
    if not value:
        raise ConfigError(
            f"缺少配置项 {key}：请在 {ROOT / '.env'} 中填写{hint}"
            f"（模板见 {ROOT / '.env.example'}），"
            f"或设置同名系统环境变量。"
        )
    return value


# ---------------------------------------------------------------- 网络

# 生产环境服务端地址（内网直连）。**不设默认值**——真实地址只存在于 .env。
HOST_URL = _get("FUNENG_HOST_URL").rstrip("/")

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

# 登录账号。**不设默认值**——真实账号只存在于 .env。
USER_NAME = _get("FUNENG_USER_NAME")

# 登录密码的 md5 —— 敏感值，只从 .env / 环境变量读，不进版本库。
PASSWORD_MD5 = _get("FUNENG_PASSWORD_MD5")

# 用户 ID。原 Node 脚本里写死在 config 里（"1990"），并拼进 Cookie 头。
# 但登录接口的响应 data.userId 就会返回它——**从登录结果里取更准**
# （换账号时不用改代码），所以这里只留一个可选项，用于服务端不返回时兜底。
USER_ID = _get("FUNENG_USER_ID")


# ---------------------------------------------------------------- 设备清单

# 设备列表（对应原 Node 脚本的 optionList）。
# 每项三个字段：fmAddress（表地址）/ meterId（表号）/ deviceCode（设备编号）。
#
# 为什么也走 .env：fmAddress / meterId 是**真实表号**，属于生产业务数据，
# 公开仓库里出现等于把厂区水表清单送上门——和地址、账号同一性质。
# 格式用 JSON 数组，一行写完，解析失败会明确报错而不是静默跳过。
DEVICES_JSON = _get("FUNENG_DEVICES")


# ---------------------------------------------------------------- 本地目录

# 验证码下载后保存到本地的目录
IMG_DIR = ROOT / "img"


# ---------------------------------------------------------------- 校验


def require_host_url() -> str:
    """返回服务端地址，未配置时抛 ConfigError。

    单独拎出来是因为地址缺失时的排查方向和密码缺失不同：
    前者要先确认 .env 存在且写了 FUNENG_HOST_URL。
    """
    return _require(
        "FUNENG_HOST_URL",
        HOST_URL,
        "生产服务端地址（形如 http://<内网IP>:<端口>）",
    )


def require_user_name() -> str:
    """返回登录账号，未配置时抛 ConfigError。"""
    return _require(
        "FUNENG_USER_NAME",
        USER_NAME,
        "登录账号名",
    )


def require_password_md5() -> str:
    """返回登录密码的 md5，未配置时抛 ConfigError。

    注意存的是**明文密码的 md5**，不是明文本身。
    """
    return _require(
        "FUNENG_PASSWORD_MD5",
        PASSWORD_MD5,
        "登录密码的 md5（不是明文密码）",
    )


def require_user_id() -> str:
    """返回用户 ID，未配置时抛 ConfigError。

    仅在服务端登录响应里没带 userId 时才需要兜底；
    正常路径是从登录结果里取（见 login.LoginResult.user_id）。
    """
    return _require(
        "FUNENG_USER_ID",
        USER_ID,
        "用户 ID（一般不需要填，登录响应会返回）",
    )


def require_devices() -> list[dict[str, str]]:
    """解析设备清单，返回 [{fmAddress, meterId, deviceCode}, ...]。

    从 .env 的 FUNENG_DEVICES 读，格式是一行 JSON 数组::

        FUNENG_DEVICES=[{"fmAddress":"...","meterId":"...","deviceCode":"..."}]

    Returns:
        设备清单；每项含 fmAddress / meterId / deviceCode 三个键。

    Raises:
        ConfigError: 未配置、不是合法 JSON、不是数组，或某项缺字段。
    """
    if not DEVICES_JSON:
        raise ConfigError(
            f"缺少配置项 FUNENG_DEVICES：请在 {ROOT / '.env'} 中填写设备清单"
            "（JSON 数组，模板见 .env.example）"
        )

    try:
        parsed = json.loads(DEVICES_JSON)
    except json.JSONDecodeError as e:
        raise ConfigError(
            f"FUNENG_DEVICES 不是合法 JSON：{e}。"
            '格式应为 [{"fmAddress":"...","meterId":"...","deviceCode":"..."}]'
        ) from e

    if not isinstance(parsed, list):
        raise ConfigError(
            f"FUNENG_DEVICES 必须是 JSON 数组，实际是 {type(parsed).__name__}"
        )

    required = ("fmAddress", "meterId", "deviceCode")
    devices: list[dict[str, str]] = []
    for index, item in enumerate(parsed):
        if not isinstance(item, dict):
            raise ConfigError(
                f"FUNENG_DEVICES 第 {index + 1} 项不是对象：{item!r}"
            )
        missing = [k for k in required if not item.get(k)]
        if missing:
            raise ConfigError(
                f"FUNENG_DEVICES 第 {index + 1} 项缺少字段：{', '.join(missing)}"
            )
        devices.append({k: str(item[k]) for k in required})

    if not devices:
        raise ConfigError("FUNENG_DEVICES 是空数组，没有可取数的设备")

    return devices
