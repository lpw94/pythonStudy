"""取数模块的单元测试：不联网、不加载 OCR 模型。

锁的行为：
1. **查询参数与原 Node 脚本一致**（startDate / endDate / fmAddress / meterId），
   且时间区间默认是「昨天 0 点 → 今天结束」——水表读数是累计值，
   只查今天会丢掉昨天累积的部分。
2. **鉴权靠两个头**：`Tw-Authorization` 请求头 **和** `Cookie` 里的同一份 token。
   只带一个拿不到数据。
3. **HTTP 200 不代表成功** —— 业务码在 body 的 code 里。
4. `code` 非 0 时抛 TokenExpiredError（调用方据此重新登录）。
5. readTime 是**毫秒时间戳**，必须原样透传，不能 str() 掉。
"""
from __future__ import annotations

from typing import Any

import pytest

from funeng_sync import meter_data
from funeng_sync.meter_data import (
    CODE_SUCCESS,
    TABLE_LIMIT,
    Device,
    MeterDataError,
    TokenExpiredError,
    build_headers,
    build_query,
    fetch_all,
    fetch_meter_data,
    format_rows,
    parse_rows,
)


@pytest.fixture
def device() -> Device:
    return Device(fm_address="FM1", meter_id="M1", device_code="DEV1")


class FakeResponse:
    """假的 requests.Response，只提供用到的两个属性。"""

    def __init__(self, body: Any, status_code: int = 200, text: str = "") -> None:
        self._body = body
        self.status_code = status_code
        self.text = text

    def json(self) -> Any:
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class FakeSession:
    """假的 Session，记录最后一次请求的参数。"""

    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        return self.response


class TestBuildQuery:
    """查询参数构造。"""

    def test_field_names_match_node_script(self, device: Device) -> None:
        """字段名必须和原 JS 一致。"""
        query = build_query(device, start_ms=1, end_ms=2)

        assert set(query) == {"startDate", "endDate", "fmAddress", "meterId"}

    def test_values_are_strings(self, device: Device) -> None:
        """时间戳要转成字符串（JS 里也是字符串）。"""
        query = build_query(device, start_ms=1792684800000, end_ms=1792771199999)

        assert query["startDate"] == "1792684800000"
        assert query["endDate"] == "1792771199999"
        assert query["fmAddress"] == "FM1"
        assert query["meterId"] == "M1"

    def test_default_range_covers_yesterday(self, device: Device) -> None:
        """默认区间是「昨天 0 点 → 今天结束」。

        水表读数是累计值，只查今天会丢掉昨天累积的那部分——
        报表上的「日用量」就全错了。
        """
        query = build_query(device)

        start = int(query["startDate"])
        end = int(query["endDate"])
        assert start < end
        # 区间跨度应大于 1 天（至少覆盖昨天 + 今天）
        assert end - start > 24 * 60 * 60 * 1000


class TestBuildHeaders:
    """请求头构造。"""

    def test_contains_tw_authorization_header(self) -> None:
        headers = build_headers("TOKEN", "1990", "someone")

        assert headers["Tw-Authorization"] == "TOKEN"

    def test_cookie_also_carries_token(self) -> None:
        """Cookie 里也要带一份 Tw-Authorization——原脚本两个都带。"""
        headers = build_headers("TOKEN", "1990", "someone")

        cookie = headers["Cookie"]
        assert "Tw-Authorization=TOKEN" in cookie
        assert "userId=1990" in cookie
        assert "userName=someone" in cookie

    def test_browser_user_agent(self) -> None:
        """部分接口会拒绝 python-requests 的默认 UA。"""
        headers = build_headers("TOKEN", "1990", "someone")

        assert "Mozilla" in headers["User-Agent"]

    def test_missing_token_raises(self) -> None:
        with pytest.raises(MeterDataError):
            build_headers("", "1990", "someone")

    def test_missing_user_id_raises(self) -> None:
        """没有 userId 时要明确报错，而不是发一个残缺 Cookie。"""
        with pytest.raises(MeterDataError) as ei:
            build_headers("TOKEN", "", "someone")

        assert "userId" in str(ei.value)


class TestParseRows:
    """响应解析。"""

    def test_success(self) -> None:
        body = {
            "code": CODE_SUCCESS,
            "data": {
                "table": [
                    {"readTime": 1792800000000, "totalFlux": 438826.66},
                    {"readTime": 1792799100000, "totalFlux": 438824.34},
                ]
            },
        }

        rows = parse_rows(body)

        assert len(rows) == 2
        assert rows[0].total_flux == 438826.66
        # readTime 必须原样保留（毫秒时间戳），不能 str() 掉
        assert rows[0].read_time == 1792800000000

    def test_empty_table(self) -> None:
        """table 为空数组不是错误，只是没数据。"""
        rows = parse_rows({"code": CODE_SUCCESS, "data": {"table": []}})

        assert rows == []

    def test_missing_table_is_tolerated(self) -> None:
        """没有 table 字段也不该抛错——当天没数据就是这个形状。"""
        rows = parse_rows({"code": CODE_SUCCESS, "data": {}})

        assert rows == []

    def test_token_expired_raises(self) -> None:
        """code 非 0 → token 失效，要单独一类让调用方重新登录。"""
        body = {"code": 401, "message": "Token失效", "data": None}

        with pytest.raises(TokenExpiredError):
            parse_rows(body)

    def test_missing_code_raises(self) -> None:
        with pytest.raises(MeterDataError):
            parse_rows({"message": "???"})

    def test_data_not_object_raises(self) -> None:
        with pytest.raises(MeterDataError):
            parse_rows({"code": CODE_SUCCESS, "data": []})

    def test_table_not_list_raises(self) -> None:
        with pytest.raises(MeterDataError):
            parse_rows({"code": CODE_SUCCESS, "data": {"table": "oops"}})

    def test_non_dict_row_is_skipped(self) -> None:
        """脏数据不该让整批解析失败。"""
        body = {
            "code": CODE_SUCCESS,
            "data": {"table": [{"readTime": 1, "totalFlux": 2}, "oops"]},
        }

        rows = parse_rows(body)

        assert len(rows) == 1


class TestFetchMeterData:
    """整条取数链路（用假 Session，不联网）。"""

    def test_request_shape(self, device: Device) -> None:
        """URL、查询参数、请求头都要对。"""
        session = FakeSession(
            FakeResponse({"code": CODE_SUCCESS, "data": {"table": []}})
        )

        fetch_meter_data(
            device, "TOKEN", "1990", "someone", session=session
        )

        call = session.calls[0]
        assert call["url"].endswith(meter_data.METER_TABLE_PATH)
        assert call["params"]["fmAddress"] == "FM1"
        assert call["params"]["meterId"] == "M1"
        assert call["headers"]["Tw-Authorization"] == "TOKEN"

    def test_limit_truncates(self, device: Device) -> None:
        """limit 对应原 JS 的 slice(0, 33)。"""
        table = [{"readTime": i, "totalFlux": i} for i in range(50)]
        session = FakeSession(
            FakeResponse({"code": CODE_SUCCESS, "data": {"table": table}})
        )

        rows = fetch_meter_data(
            device, "TOKEN", "1990", "someone", session=session, limit=TABLE_LIMIT
        )

        assert len(rows) == TABLE_LIMIT

    def test_non_json_response_raises(self, device: Device) -> None:
        """返回的不是 JSON 时要报出人能看懂的错。"""
        session = FakeSession(
            FakeResponse(
                ValueError("no json"), status_code=500, text="<html>502</html>"
            )
        )

        with pytest.raises(MeterDataError) as ei:
            fetch_meter_data(device, "TOKEN", "1990", "someone", session=session)

        assert "502" in str(ei.value)


class TestFetchAll:
    """多设备取数。"""

    def test_uses_config_devices(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """设备清单默认从配置里读。"""
        monkeypatch.setattr(
            meter_data.config,
            "DEVICES_JSON",
            '[{"fmAddress":"A","meterId":"1","deviceCode":"D1"}]',
        )
        session = FakeSession(
            FakeResponse({"code": CODE_SUCCESS, "data": {"table": []}})
        )

        result = fetch_all("TOKEN", "1990", "someone", session=session)

        assert list(result) == ["D1"]


class TestFormatRows:
    """打印格式。"""

    def test_empty(self) -> None:
        assert format_rows([]) == "（无数据）"

    def test_reads_millis_as_datetime(self) -> None:
        """毫秒时间戳要显示成可读时间，而不是一串数字。"""
        rows = parse_rows(
            {
                "code": CODE_SUCCESS,
                "data": {
                    "table": [{"readTime": 1792800000000, "totalFlux": 438826.66}]
                },
            }
        )

        text = format_rows(rows)

        assert "1792800000000" not in text
        assert "累计流量=438826.66" in text
