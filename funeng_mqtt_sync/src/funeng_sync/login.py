"""登录：拿验证码 -> 识别 -> 用账号密码换 JWT token。

对标原 Node 脚本 index.js 里的登录段落：

    const url = hostUrl + '/api/auth/jwt/token'
    let params = {
      key: dateTime,                 // 验证码图片 URL 上的那个毫秒时间戳
      loginName: userName,
      password: '<明文密码的 md5>',   // 原脚本里是硬编码的 32 位 md5
      verificationCode: code,        // 识别出来的 4 位验证码
    }
    axios.post(url, params, { headers: {...} })

接口返回（实测）：
    成功 {"code":0,"message":"SUCC","data":{"token":"...","name":"...","userId":1990}}
    验证码错 {"code":-1,"message":"验证码错误","data":null}
    验证码无效 {"code":-1,"message":"验证码无效","data":null}
    账号密码错 {"code":-1,"message":"用户名或密码错误","data":null}

注意：**HTTP 状态码永远是 200**，业务成败只看 body 里的 code。
所以不能用 resp.ok 判断成功，必须解析 JSON。

运行（用 3.12 环境，ddddocr 需要 <=3.12）：
    E:/workBuddy/pythonStudy/.py312/python.exe -m funeng_sync.login
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from funeng_sync import config, net
from funeng_sync.login_test import (
    CAPTCHA_LENGTH,
    MAX_RETRY,
    Captcha,
    CaptchaError,
    ConfigMissingError,
    download_and_recognize,
)

# 登录接口固定的请求头（照搬原 Node 脚本）
LOGIN_HEADERS = {
    "Content-Type": "application/json;charset=UTF-8",
    "Accept": "application/json, text/plain, */*",
}

# 业务成功码：body 里的 code == 0 才算成功
CODE_SUCCESS = 0

# 服务端在「验证码不对」时返回的 message。命中它说明是识别错了，
# 换一张验证码重试即可——但每张验证码只能用一次，必须重新下载。
MSG_CAPTCHA_ERROR = "验证码错误"

# 登录失败后重试的整体次数（每次重试都会重新下载一张验证码）
MAX_LOGIN_RETRY = 5

# 两次登录尝试之间的间隔（秒）。原 Node 脚本用的是 10 秒——
# 连续打服务端容易触发风控，这里保持同样的量级。
RETRY_INTERVAL = 10


class LoginError(RuntimeError):
    """登录失败（账号密码错误、重试用尽等）。"""


@dataclass(frozen=True)
class LoginResult:
    """一次登录请求的结果。

    Attributes:
        code: 业务码，0 表示成功。
        message: 服务端返回的描述。
        token: 成功时的 JWT token，失败为 None。
        user_id: 服务端返回的用户 ID。取数接口的 Cookie 头里要用它，
            所以从登录结果里带出来，而不是在代码里写死。
        raw: 服务端的原始响应体。
    """

    code: int
    message: str
    token: str | None
    user_id: str | None
    raw: dict[str, Any]

    @property
    def ok(self) -> bool:
        """是否登录成功。"""
        return self.code == CODE_SUCCESS and bool(self.token)


def build_login_payload(captcha: Captcha) -> dict[str, Any]:
    """构造登录请求体。

    Args:
        captcha: 含 key（时间戳）和 code（验证码）的验证码对象。

    Returns:
        请求体字典。

    Raises:
        LoginError: 没配置密码 md5 时抛出——带着空密码去请求只会得到
            「用户名或密码错误」，掩盖真正的问题。
    """
    if not config.PASSWORD_MD5:
        raise LoginError(
            "未配置密码 md5：请在项目根目录 .env 里设置 FUNENG_PASSWORD_MD5"
            "（明文密码的 md5，不是明文本身）"
        )

    try:
        user_name = config.require_user_name()
    except config.ConfigError as e:
        # 配置缺失属于「环境没配好」，不是「凭据不对」——
        # 归一成 LoginError，调用方只需捕获一种异常。
        raise LoginError(str(e)) from e

    return {
        "key": captcha.key,
        "loginName": user_name,
        "password": config.PASSWORD_MD5,
        "verificationCode": captcha.code,
    }


def parse_response(body: dict[str, Any]) -> LoginResult:
    """把服务端响应解析成 LoginResult。

    Args:
        body: 响应 JSON。

    Returns:
        解析后的结果。

    Raises:
        LoginError: 响应结构不符合预期（缺 code / data 不是字典）。
    """
    if "code" not in body:
        raise LoginError(f"登录响应缺少 code 字段：{body}")

    data = body.get("data")
    token = data.get("token") if isinstance(data, dict) else None
    # userId 是数字（1990 这种），转成 str 方便直接拼进 Cookie 头
    raw_user_id = data.get("userId") if isinstance(data, dict) else None
    user_id = str(raw_user_id) if raw_user_id is not None else None

    return LoginResult(
        code=body.get("code"),
        message=body.get("message", ""),
        token=token,
        user_id=user_id,
        raw=body,
    )


def request_token(captcha: Captcha) -> LoginResult:
    """向 /api/auth/jwt/token 发一次登录请求。

    Args:
        captcha: 本次使用的验证码（含 key 与 code）。

    Returns:
        登录结果。

    Raises:
        LoginError: 请求本身失败（网络异常、响应不是合法 JSON 等）。
    """
    payload = build_login_payload(captcha)

    # 地址缺失时 requests 会抛 MissingSchema("Invalid URL '/api/...'")，
    # 完全指不到「.env 没写 FUNENG_HOST_URL」。这里先校验一道，
    # 把「环境没配好」和「服务端报错」区分开。
    try:
        config.require_host_url()
    except config.ConfigError as e:
        raise LoginError(str(e)) from e

    with net.new_session() as session:
        resp = session.post(
            config.LOGIN_URL,
            json=payload,
            headers=LOGIN_HEADERS,
            timeout=config.HTTP_TIMEOUT,
        )

    try:
        body = resp.json()
    except ValueError as e:
        raise LoginError(
            f"登录接口返回的不是 JSON（HTTP {resp.status_code}）：{resp.text[:200]}"
        ) from e

    if not isinstance(body, dict):
        raise LoginError(f"登录接口返回的不是 JSON 对象：{body!r}")

    return parse_response(body)


def login(
    max_retry: int = MAX_LOGIN_RETRY,
    length: int = CAPTCHA_LENGTH,
) -> LoginResult:
    """完成一次完整登录：下载验证码 -> 识别 -> 换 token。

    「验证码错误」会触发重试：识别难免出错（把 5 认成 b 这类），
    每张验证码一次性有效，所以重试必须**重新下载一张**。

    Args:
        max_retry: 最多尝试几轮。
        length: 期望的验证码位数。

    Returns:
        登录成功的结果。

    Raises:
        LoginError: 账号密码错误，或重试用尽仍未成功。
    """
    last_result: LoginResult | None = None
    last_err = ""

    for attempt in range(1, max_retry + 1):
        try:
            captcha = download_and_recognize(max_retry=MAX_RETRY, length=length)
        except CaptchaError as e:
            last_err = str(e)
            print(f"[{attempt}/{max_retry}] 取验证码失败：{last_err}")
            if isinstance(e, ConfigMissingError):
                # 配置没配好，再试多少次都一样，直接中止。
                raise LoginError(str(e)) from e
            continue

        result = request_token(captcha)
        print(
            f"[{attempt}/{max_retry}] 登录响应 code={result.code} "
            f"message={result.message!r}"
        )

        if result.ok:
            return result

        last_result = result

        # 验证码错了：换一张重新来。其它错误（账号密码错等）重试也没用，
        # 直接抛错——继续重试只会反复触发服务端的失败次数限制。
        if result.message != MSG_CAPTCHA_ERROR:
            raise LoginError(f"登录失败：{result.message}（code={result.code}）")

        if attempt < max_retry:
            print(f"[{attempt}/{max_retry}] {RETRY_INTERVAL} 秒后重试")
            time.sleep(RETRY_INTERVAL)

    detail = (
        f"{last_result.message}（code={last_result.code}）"
        if last_result
        else last_err or "无"
    )
    raise LoginError(f"尝试 {max_retry} 次仍未登录成功：{detail}")


def main() -> None:
    """跑一次登录并打印服务端返回的原始 JSON。"""
    try:
        result = login()
    except LoginError as e:
        print(f"登录失败：{e}")
        return

    print("登录成功")
    print(json.dumps(result.raw, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
