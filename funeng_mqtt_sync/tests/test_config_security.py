"""敏感配置处理的单元测试。

锁的行为（这些是**安全边界**，不是普通功能）：

1. `config.py` 里**不出现任何真实的地址与账号**——敏感项没有默认值，
   缺失时由 `require_*()` 显式抛 `ConfigError`。
2. 兜底默认值就是泄露的源头：宁可启动失败，也不要用硬编码值假装正常。
3. **配置缺失不重试**——重试不会让配置凭空出现，只会刷 5 遍同样的错。
4. 地址缺失时要报「.env 没写 FUNENG_HOST_URL」，而不是 requests 的
   `MissingSchema("Invalid URL '/api/...'")` —— 后者完全指不到根因。
"""
from __future__ import annotations

import pytest

from funeng_sync import config as config_mod
from funeng_sync import login as login_mod
from funeng_sync import login_test as lt_mod
from funeng_sync.login import LoginError, build_login_payload
from funeng_sync.login_test import Captcha, ConfigMissingError, download_captcha


class TestConfigHasNoSensitiveDefaults:
    """源码里不能有真实的地址与账号。"""

    def test_host_url_has_no_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """FUNENG_HOST_URL 没配时就是空串，不该有兜底地址。"""
        monkeypatch.setattr(config_mod, "HOST_URL", "")

        assert config_mod.HOST_URL == ""

    def test_user_name_has_no_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """FUNENG_USER_NAME 同理。"""
        monkeypatch.setattr(config_mod, "USER_NAME", "")

        assert config_mod.USER_NAME == ""

    def test_password_has_no_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(config_mod, "PASSWORD_MD5", "")

        assert config_mod.PASSWORD_MD5 == ""


class TestRequireHelpers:
    """require_* 的报错必须指明「去哪填」。"""

    def test_require_host_url_raises_with_hint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(config_mod, "HOST_URL", "")

        with pytest.raises(config_mod.ConfigError) as ei:
            config_mod.require_host_url()

        msg = str(ei.value)
        assert "FUNENG_HOST_URL" in msg
        assert ".env" in msg

    def test_require_user_name_raises_with_hint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(config_mod, "USER_NAME", "")

        with pytest.raises(config_mod.ConfigError) as ei:
            config_mod.require_user_name()

        assert "FUNENG_USER_NAME" in str(ei.value)

    def test_require_password_md5_raises_with_hint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(config_mod, "PASSWORD_MD5", "")

        with pytest.raises(config_mod.ConfigError) as ei:
            config_mod.require_password_md5()

        assert "FUNENG_PASSWORD_MD5" in str(ei.value)

    def test_require_returns_value_when_present(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(config_mod, "HOST_URL", "http://10.0.0.1:8080")

        assert config_mod.require_host_url() == "http://10.0.0.1:8080"


class TestMissingConfigIsNotRetried:
    """配置缺失必须立即中止，不能重试 5 次。"""

    def test_download_captcha_raises_config_missing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        """没配地址时直接抛 ConfigMissingError。"""
        monkeypatch.setattr(config_mod, "HOST_URL", "")

        with pytest.raises(ConfigMissingError) as ei:
            download_captcha(save_dir=tmp_path)

        assert "FUNENG_HOST_URL" in str(ei.value)

    def test_config_missing_is_captcha_error_subclass(self) -> None:
        """保持向后兼容：老的 except CaptchaError 仍然能兜住。"""
        assert issubclass(ConfigMissingError, lt_mod.CaptchaError)

    def test_download_and_recognize_does_not_retry(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        """重试循环遇到配置缺失要立刻抛出，不刷 5 遍。"""
        calls = {"n": 0}

        def _fake_download(**_k):  # type: ignore[no-untyped-def]
            calls["n"] += 1
            raise ConfigMissingError("未配置服务端地址")

        monkeypatch.setattr(lt_mod, "download_captcha", _fake_download)

        with pytest.raises(ConfigMissingError):
            lt_mod.download_and_recognize(max_retry=5, save_dir=tmp_path)

        # 只试了 1 次，不是 5 次
        assert calls["n"] == 1

    def test_login_aborts_on_config_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """login() 遇到配置缺失立刻中止。"""
        calls = {"n": 0}

        def _fake_captcha(**_k):  # type: ignore[no-untyped-def]
            calls["n"] += 1
            raise ConfigMissingError("未配置服务端地址")

        monkeypatch.setattr(login_mod, "download_and_recognize", _fake_captcha)

        with pytest.raises(LoginError) as ei:
            login_mod.login()

        assert "未配置服务端地址" in str(ei.value)
        assert calls["n"] == 1


class TestRequestTokenValidatesHostUrl:
    """地址缺失时的报错要指向根因，而不是 requests 的 MissingSchema。"""

    def test_raises_login_error_not_missing_schema(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(config_mod, "HOST_URL", "")
        monkeypatch.setattr(config_mod, "PASSWORD_MD5", "0" * 32)
        monkeypatch.setattr(config_mod, "USER_NAME", "someone")

        captcha = Captcha(path=None, key=1, code="ab12")  # type: ignore[arg-type]

        with pytest.raises(LoginError) as ei:
            login_mod.request_token(captcha)

        msg = str(ei.value)
        assert "FUNENG_HOST_URL" in msg
        # 关键：不能是 requests 那个指向不明的错
        assert "MissingSchema" not in msg
        assert "Invalid URL" not in msg


class TestBuildPayloadRequiresUserName:
    """账号缺失也要明确报错。"""

    def test_missing_user_name_raises_login_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(config_mod, "PASSWORD_MD5", "0" * 32)
        monkeypatch.setattr(config_mod, "USER_NAME", "")

        captcha = Captcha(path=None, key=1, code="ab12")  # type: ignore[arg-type]

        with pytest.raises(LoginError) as ei:
            build_login_payload(captcha)

        assert "FUNENG_USER_NAME" in str(ei.value)


class TestEnvExampleIsSafe:
    """模板文件里不能出现真实值。"""

    def test_env_example_contains_only_placeholders(self) -> None:
        from pathlib import Path

        env_example = Path(__file__).resolve().parent.parent / ".env.example"
        text = env_example.read_text(encoding="utf-8")

        # 模板里不允许出现「能直接用的值」
        assert "FUNENG_PASSWORD_MD5=your_login_password_md5" not in text
        assert "FUNENG_PASSWORD_MD5=<32位小写md5>" in text
        # 真实地址不能出现
        assert "10.0.0.1" not in text
        assert "your_account" not in text
