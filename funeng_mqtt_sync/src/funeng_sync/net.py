"""网络层：统一的 HTTP 会话构造。

为什么要专门封一个会话，而不是各处直接 requests.get：

requests 默认会读取环境变量 http_proxy / https_proxy。本机装了企业代理，
而目标服务是**内网直连**地址，走代理时实测出现两种坏结果：

- 下载验证码拿到 **0 字节**（连接被代理吞掉，requests 不报错，只是空响应）
- 下载到 **44 字节的 JSON**（{"code":20000,"message":"Token不能为空"}）

两种都会被下游的「图片魔数校验」拦下，但白白浪费一次验证码，还让报错
信息指向错误的方向。内网请求统一用 trust_env=False 绕过环境代理。

用法：
    from funeng_sync import net

    with net.new_session() as session:
        resp = session.get(url, timeout=10)
"""
from __future__ import annotations

import requests

from funeng_sync import config


def new_session() -> requests.Session:
    """新建一个 HTTP 会话。

    Returns:
        配置好代理策略的 Session。调用方负责 close（或用 with）。
    """
    session = requests.Session()
    # trust_env=False 会同时忽略 http_proxy / https_proxy / .netrc，
    # 避免内网地址被塞进企业代理的链路里。
    session.trust_env = not config.BYPASS_ENV_PROXY
    return session


__all__ = ["new_session"]
