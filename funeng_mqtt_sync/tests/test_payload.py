"""payload 构造的单元测试（对应 getData 里的 obj / payload 结构）。"""
from funeng_sync.http_client import build_payload


def test_build_payload() -> None:
    p = build_payload("XT200025", "2026-10-13 00:00:00", 12.5)
    assert p[0]["deviceCode"] == "XT200025"
    assert p[0]["T_2026-10-13 00:00:00"]["datas"]["internetTraffic"] == 12.5


def test_build_payload_key_prefix() -> None:
    p = build_payload("XT200026", "2026-10-13 08:00:00", 0)
    assert "T_2026-10-13 08:00:00" in p[0]
    assert p[0]["T_2026-10-13 08:00:00"]["datas"]["internetTraffic"] == 0
