"""payload 构造的单元测试（对应 getData 里的 obj / payload 结构）。

这两条用例锁的是「T_ 前缀」—— 少写一个字符后端会静默丢数据，
是整个同步链路里最不容易发现的一类错，所以专门测。
"""
from funeng_sync.payload import build_payload


def test_build_payload() -> None:
    p = build_payload("XT001", "2026-10-13 00:00:00", 12.5)
    assert p[0]["deviceCode"] == "XT001"
    assert p[0]["T_2026-10-13 00:00:00"]["datas"]["internetTraffic"] == 12.5


def test_build_payload_key_prefix() -> None:
    p = build_payload("XT002", "2026-10-13 08:00:00", 0)
    assert "T_2026-10-13 08:00:00" in p[0]
    assert p[0]["T_2026-10-13 08:00:00"]["datas"]["internetTraffic"] == 0
