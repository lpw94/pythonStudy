"""登录模块的单元测试：不联网、不加载 OCR 模型。

锁的行为：
1. **请求体字段与原 Node 脚本完全一致**（key / loginName / password /
   verificationCode），字段名拼错服务端一律不认。
2. **HTTP 200 不等于成功** —— 业务码在 body 的 code 字段里，
   失败时同样是 200 + {"code":-1,...}。
3. **验证码错误才重试**，账号密码错误直接抛错（重试只会撞风控）。
4. 重试时必须重新取验证码（key 要换）。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from funeng_sync import login as login_mod
from funeng_sync.login import (
    CODE_SUCCESS,
    MSG_CAPTCHA_ERROR,
    LoginError,
    build_login_payload,
    login,
    parse_response,
)
from funeng_sync.login_test import Captcha


@pytest.fixture(autouse=True)
def _password(monkeypatch: pytest.MonkeyPatch) -> None:
    """给测试注入一个占位密码 md5。

    真实值在 .env 里（不进版本库），测试用假值即可——
    这里只关心请求体里有没有正确带上 password 字段。
    """
    monkeypatch.setattr(login_mod.config, "PASSWORD_MD5", "0" * 32)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """去掉重试间隔的 sleep。"""
    monkeypatch.setattr(login_mod.time, "sleep", lambda _s: None)


def _captcha(code: str = "ab12", key: int = 1792757479692) -> Captcha:
    return Captcha(path=Path("captcha.jpg"), key=key, code=code)


class TestBuildLoginPayload:
    """请求体构造。"""

    def test_field_names_match_node_script(self) -> None:
        """字段名必须和原 JS 一致：key / loginName / password / verificationCode。"""
        payload = build_login_payload(_captcha())

        assert set(payload) == {
            "key",
            "loginName",
            "password",
            "verificationCode",
        }

    def test_key_is_the_timestamp(self) -> None:
        """key 必须是验证码图片 URL 上的那个时间戳。"""
        payload = build_login_payload(_captcha(key=1792757479692))

        assert payload["key"] == 1792757479692

    def test_verification_code_is_carried_over(self) -> None:
        payload = build_login_payload(_captcha(code="gnwd"))

        assert payload["verificationCode"] == "gnwd"

    def test_missing_password_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """没配密码 md5 时要明确报错，而不是发一个空密码的请求。"""
        monkeypatch.setattr(login_mod.config, "PASSWORD_MD5", "")

        with pytest.raises(LoginError) as ei:
            build_login_payload(_captcha())

        assert "FUNENG_PASSWORD_MD5" in str(ei.value)


class TestParseResponse:
    """响应解析。"""

    def test_success(self) -> None:
        body = {
            "code": 0,
            "message": "SUCC",
            "data": {"token": "E59C566B5E6542ACB0543CC4FE0DEB60", "userId": 1990},
        }

        result = parse_response(body)

        assert result.ok is True
        assert result.token == "E59C566B5E6542ACB0543CC4FE0DEB60"

    def test_captcha_error_is_http_200(self) -> None:
        """服务端在验证码错时返回 HTTP 200 + code=-1。"""
        body = {"code": -1, "message": MSG_CAPTCHA_ERROR, "data": None}

        result = parse_response(body)

        assert result.ok is False
        assert result.code == -1
        assert result.message == MSG_CAPTCHA_ERROR

    def test_wrong_password(self) -> None:
        body = {"code": -1, "message": "用户名或密码错误", "data": None}

        result = parse_response(body)

        assert result.ok is False
        assert result.message == "用户名或密码错误"

    def test_code_zero_without_token_is_not_ok(self) -> None:
        """code=0 但没有 token，仍然不能算成功。"""
        body = {"code": CODE_SUCCESS, "message": "SUCC", "data": None}

        result = parse_response(body)

        assert result.ok is False

    def test_missing_code_raises(self) -> None:
        with pytest.raises(LoginError):
            parse_response({"message": "???"})


class TestLogin:
    """整体登录流程。"""

    def test_success_on_first_try(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """一次就成功 → 不再重试。"""
        calls = {"captcha": 0, "request": 0}

        def _fake_captcha(**_k):  # type: ignore[no-untyped-def]
            calls["captcha"] += 1
            return _captcha()

        def _fake_request(captcha: Captcha):  # type: ignore[no-untyped-def]
            calls["request"] += 1
            return parse_response(
                {"code": 0, "message": "SUCC", "data": {"token": "T"}}
            )

        monkeypatch.setattr(login_mod, "download_and_recognize", _fake_captcha)
        monkeypatch.setattr(login_mod, "request_token", _fake_request)

        result = login()

        assert result.ok is True
        assert result.token == "T"
        assert calls["request"] == 1

    def test_captcha_error_triggers_retry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """验证码错误 → 重新取验证码再试。"""
        seen_keys: list[int] = []

        def _fake_captcha(**_k):  # type: ignore[no-untyped-def]
            # 每次返回不同的 key，模拟「换了一张新图」
            return _captcha(key=1000 + len(seen_keys) + 1)

        def _fake_request(captcha: Captcha):  # type: ignore[no-untyped-def]
            seen_keys.append(captcha.key)
            if len(seen_keys) < 3:
                return parse_response(
                    {"code": -1, "message": MSG_CAPTCHA_ERROR, "data": None}
                )
            return parse_response(
                {"code": 0, "message": "SUCC", "data": {"token": "T"}}
            )

        monkeypatch.setattr(login_mod, "download_and_recognize", _fake_captcha)
        monkeypatch.setattr(login_mod, "request_token", _fake_request)

        result = login()

        assert result.ok is True
        # 三次请求的 key 必须各不相同
        assert len(seen_keys) == 3
        assert len(set(seen_keys)) == 3

    def test_wrong_password_does_not_retry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """账号密码错误 → 直接抛错，不重试（重试只会撞风控）。"""
        calls = {"request": 0}

        def _fake_captcha(**_k):  # type: ignore[no-untyped-def]
            return _captcha()

        def _fake_request(captcha: Captcha):  # type: ignore[no-untyped-def]
            calls["request"] += 1
            return parse_response(
                {"code": -1, "message": "用户名或密码错误", "data": None}
            )

        monkeypatch.setattr(login_mod, "download_and_recognize", _fake_captcha)
        monkeypatch.setattr(login_mod, "request_token", _fake_request)

        with pytest.raises(LoginError) as ei:
            login()

        assert "用户名或密码错误" in str(ei.value)
        assert calls["request"] == 1

    def test_exhausted_retries_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """一直验证码错 → 用尽次数后抛错，不能无限重试。"""
        calls = {"request": 0}

        def _fake_captcha(**_k):  # type: ignore[no-untyped-def]
            return _captcha()

        def _fake_request(captcha: Captcha):  # type: ignore[no-untyped-def]
            calls["request"] += 1
            return parse_response(
                {"code": -1, "message": MSG_CAPTCHA_ERROR, "data": None}
            )

        monkeypatch.setattr(login_mod, "download_and_recognize", _fake_captcha)
        monkeypatch.setattr(login_mod, "request_token", _fake_request)

        with pytest.raises(LoginError) as ei:
            login(max_retry=3)

        assert calls["request"] == 3
        assert "3" in str(ei.value)
