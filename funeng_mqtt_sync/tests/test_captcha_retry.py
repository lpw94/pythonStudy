"""重试循环的单元测试：用假对象替换下载/识别，不联网不加载模型。

要锁的行为：
- 第一次识别长度不对 → 会重新下载再识别
- 连续失败到上限 → 抛 CaptchaError（而不是永远重试下去）
- 下载失败（服务端返回非图片）→ 也算一次尝试，最终抛错
- 中途成功 → 立刻返回，不再重试
"""
from __future__ import annotations

import pytest

from funeng_sync import login_test
from funeng_sync.login_test import CaptchaError, download_and_recognize


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """把重试间隔的 sleep 去掉，测试不卡时间。"""
    monkeypatch.setattr(login_test.time, "sleep", lambda _s: None)


def _fake_download(
    monkeypatch: pytest.MonkeyPatch, paths: list[str], fail_times: int = 0
) -> None:
    """替换 download_captcha：按顺序返回给定路径，前 fail_times 次抛错。"""
    it = iter(paths)
    calls = {"n": 0}

    def _dl(*_a, **_k):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        if calls["n"] <= fail_times:
            raise CaptchaError("内容不是图片：Token不能为空")
        return next(it)

    monkeypatch.setattr(login_test, "download_captcha", _dl)


def _fake_recognize(monkeypatch: pytest.MonkeyPatch, results: list[str]) -> None:
    """替换 recognize：按顺序返回识别结果。"""
    it = iter(results)
    monkeypatch.setattr(login_test, "recognize", lambda _p: next(it))


def test_retry_until_valid(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """前两次识别长度不对，第三次正确 → 应成功返回且只下载 3 次。"""
    _fake_download(monkeypatch, ["a.jpg", "b.jpg", "c.jpg"])
    _fake_recognize(monkeypatch, ["ab1", "abcde", "ab12"])

    img, text = download_and_recognize(max_retry=5, save_dir=tmp_path)

    assert text == "ab12"
    assert img == "c.jpg"


def test_success_on_first_try(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """一次就对 → 不重试。"""
    _fake_download(monkeypatch, ["a.jpg"])
    _fake_recognize(monkeypatch, ["ab12"])

    img, text = download_and_recognize(max_retry=5, save_dir=tmp_path)

    assert (img, text) == ("a.jpg", "ab12")


def test_exhausted_raises(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """一直识别不对 → 用尽次数后抛 CaptchaError，不能无限重试。"""
    _fake_download(monkeypatch, ["a.jpg", "b.jpg", "c.jpg"])
    _fake_recognize(monkeypatch, ["ab1", "ab1", "ab1"])

    with pytest.raises(CaptchaError) as ei:
        download_and_recognize(max_retry=3, save_dir=tmp_path)

    assert "3" in str(ei.value)
    assert "ab1" in str(ei.value)


def test_download_failure_raises(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """下载一直失败（Token 失效等）→ 同样最终抛错。"""
    _fake_download(monkeypatch, [], fail_times=99)

    with pytest.raises(CaptchaError):
        download_and_recognize(max_retry=2, save_dir=tmp_path)


def test_download_failure_then_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """下载失败一次后恢复正常 → 应继续并成功。"""
    _fake_download(monkeypatch, ["a.jpg"], fail_times=1)
    _fake_recognize(monkeypatch, ["ab12"])

    _img, text = download_and_recognize(max_retry=3, save_dir=tmp_path)

    assert text == "ab12"


def test_recognize_exception_is_retried(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """识别抛异常（图片损坏）→ 也应重试，而不是直接崩。"""
    calls = {"n": 0}

    def _rec(_p: str) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            raise CaptchaError("识别失败：cannot identify image file")
        return "ab12"

    _fake_download(monkeypatch, ["a.jpg", "b.jpg"])
    monkeypatch.setattr(login_test, "recognize", _rec)

    _img, text = download_and_recognize(max_retry=3, save_dir=tmp_path)

    assert text == "ab12"
    assert calls["n"] == 2


def test_max_retry_one_does_not_retry(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """max_retry=1 表示只试一次，不重试。"""
    _fake_download(monkeypatch, ["a.jpg"])
    _fake_recognize(monkeypatch, ["ab1"])

    with pytest.raises(CaptchaError):
        download_and_recognize(max_retry=1, save_dir=tmp_path)
