"""安全核心：密码哈希 + JWT 签发/校验。

对标前端：
- bcrypt 哈希 ≈ 前端提交前不加密、但后端必须 bcrypt 存（前端不该碰密码）
- JWT ≈ jsonwebtoken，签发/校验是同一个库的两组 API
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from ..config import settings

# 直接用 bcrypt 库，不套 passlib：
# passlib 1.7.4 的 `detect_wrap_bug` 逻辑在 bcrypt 4.1+ 会抛
# 「password cannot be longer than 72 bytes」，而 bcrypt 4.x 本身
# 已能正确处理（自动截断 + 显式报错），没必要多引一层。
# 对标前端 bcryptjs / node bcrypt 的 hashSync + compareSync。

# bcrypt 的密码长度上限是 72 字节（不是字符）。超长密码按 bcrypt 官方行为截断。
# 这里显式截断而不是让 bcrypt 报错，避免用户输入超长密码时 500。
MAX_PASSWORD_BYTES = 72


def _truncate(password: str) -> bytes:
    """按 UTF-8 字节截断到 bcrypt 上限。

    bcrypt 4.x 在超长时会直接抛异常，所以要自己截。
    用 bytes 切片而不是 str 切片——按字符切可能切出半个多字节字符。
    """
    return password.encode("utf-8")[:MAX_PASSWORD_BYTES]


def hash_password(password: str) -> str:
    """明文 → bcrypt 哈希。入库前必须过这一道。

    gensalt() 生成随机盐，同一个密码两次结果不同——这正是能安全校验的原因。
    """
    return bcrypt.hashpw(_truncate(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """校验明文和哈希是否匹配。

    哈希格式不对时 bcrypt 会抛异常，这里统一吞掉返回 False——
    对标前端「登录失败就提示失败」，不区分「用户不存在」和「密码错」
    （区分了等于告诉攻击者哪些用户名存在）。
    """
    try:
        return bcrypt.checkpw(_truncate(plain), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _create_token(
    subject: str,
    token_type: str,
    expires_delta: timedelta,
    extra: dict[str, Any] | None = None,
) -> str:
    """签发一个 JWT。

    JWT 三段式：header.payload.signature（base64url 编码，不是加密）。
    payload 里放业务数据 + 过期时间，signature 用来防篡改。

    `jti`（JWT ID）是这个令牌的唯一标识：
    - 登出时把 jti 存进黑名单表即可让单个令牌失效
    - refresh token 轮换时用来识别「这是一次续期不是复用」
    """
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,          # subject：令牌代表谁（这里是 user id）
        "type": token_type,      # access / refresh
        "iat": now,              # issued at
        "exp": now + expires_delta,  # expiration
        "jti": uuid.uuid4().hex,  # JWT ID
    }
    if extra:
        payload.update(extra)

    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: int, username: str) -> str:
    """签发访问令牌：短有效期（默认 12 小时），随请求携带。"""
    return _create_token(
        subject=str(user_id),
        token_type="access",
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        extra={"username": username},
    )


def create_refresh_token(user_id: int, username: str) -> str:
    """签发刷新令牌：长有效期（默认 7 天），只用来换新的 access token。

    为什么需要两个令牌：
    - access 短命，泄露了影响有限
    - refresh 长命，但只在换 token 时用一次，可以单独做黑名单/轮换
    这是「双令牌」标准做法，对标前端 axios 拦截器里的 refresh 流程。
    """
    return _create_token(
        subject=str(user_id),
        token_type="refresh",
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
        extra={"username": username},
    )


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any] | None:
    """解析并校验 JWT。

    返回 payload；任何一步失败（过期 / 签名不对 / 类型不对）都返回 None。
    调用方（依赖层）据此抛 401。

    注意：jwt.decode 会自己校验 exp 过期时间，不用手动比对。
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError:
        return None

    if payload.get("type") != expected_type:
        return None
    return payload
