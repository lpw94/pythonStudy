"""示例：被导入的「另一个文件」（配置 / 常量模块）。

演示 Python 模块如何向外部暴露变量、函数、类。
本文件只放纯数据，不写任何「每次调用都要执行」的业务逻辑——
模块顶层代码在 import 时只执行一次，且会被缓存进 sys.modules。
"""

from __future__ import annotations

# 不可变常量（str / int / float 等）：from import 后重新赋值不会影响源模块
APP_NAME: str = "funeng-demo"
BASE_URL: str = "http://10.0.0.1:8080"
TIMEOUT: int = 10

# 可变对象（list / dict）：from import 后调用 .append / 改 key 会作用到同一对象
ALLOWED_CODES: list[str] = ["xsrx", "zgqj", "xbaq"]


def build_url(path: str) -> str:
    """拼接完整接口地址。

    Args:
        path: 接口路径，例如 "/api/auth/verificationCode/captcha-image/123"

    Returns:
        拼接后的完整 URL
    """
    return f"{BASE_URL}{path}"
