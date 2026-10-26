"""取数：登录换到 token 之后，拉水表实时数据表。

对标原 Node 脚本 index.js 里的 getData：

    const url = hostUrl
        + '/api/largeCustomer/operationManagement/meterRealTimeDataTable'
    const params = {
      startDate, endDate,      // 毫秒时间戳
      fmAddress, meterId,      // 表地址 + 表号
    }
    const headers = {
      'Content-Type': 'application/json;charset=UTF-8',
      'Accept': 'application/json, text/plain, */*',
      'Tw-Authorization': token,
      Cookie: `userId=${USER_ID}; userName=${USER_NAME}; Tw-Authorization=${token};`,
    }
    axios.get(url, { params, headers })

三个要点（都是实测踩出来的）：

1. **鉴权靠两个头**：`Tw-Authorization` 请求头 **和** `Cookie` 里的
   `Tw-Authorization`。原脚本两个都带——只带请求头实测拿不到数据。
   Cookie 里还带了 `userId` 与 `userName`，`userId` 用登录响应里的
   `data.userId`，不用在代码里写死。

2. **时间区间是毫秒时间戳的字符串**，不是日期字符串。
   原脚本取「昨天 0 点 → 今天 23:59:59.999」，这样返回的表里
   一定含有昨天的累计流量（水表读数是累计值，跨天要看到前一天末尾那一条）。
   见 time_utils.yesterday_start_millis / end_of_day_millis。

3. **接口用 HTTP 200 表达一切错误**，业务码在 body 的 `code` 里。
   `code` 非 0 就是 token 失效或参数不对——原脚本据此触发重新登录。

本阶段**只打印数据，不上报 MQTT**（上报是下一阶段的事）。
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from funeng_sync import config, net
from funeng_sync.time_utils import (
    end_of_day_millis,
    format_read_time,
    is_top_of_hour,
    yesterday_start_millis,
)

# 取数接口路径（拼在 HOST_URL 后面）
METER_TABLE_PATH = "/api/largeCustomer/operationManagement/meterRealTimeDataTable"

# 业务成功码：body 里的 code == 0 才算成功
CODE_SUCCESS = 0

# 原 JS 里 `[...data.data.table].slice(0, 33)` 的 33。
# 服务端返回的是**倒序**（最新在前），33 条大约覆盖一天多的整点数据——
# 上报时只取这么多，够用又不至于把 MQTT 灌爆。
# 本阶段只打印，所以默认**不截断**（limit=None），需要复刻原行为时传 33。
TABLE_LIMIT = 33

# 部分接口会拒绝 python-requests 的默认 UA，原脚本给 session 统一换了浏览器 UA。
# 只对取数接口加——验证码与登录那条链路已实测通过，不去动它。
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# 取数的超时比验证码长（原 JS 用的是 15s，验证码用 10s）
DATA_TIMEOUT = 15

# `--excel` 不带路径时用它占位：走默认输出目录（out/水表数据_<时间戳>.xlsx）。
# 用一个显式常量而不是 None，是因为 None 已经被「不导出」占用了。
DEFAULT_EXCEL_FLAG = "__default__"


class MeterDataError(RuntimeError):
    """取数失败（接口报错、响应结构异常等）。"""


class TokenExpiredError(MeterDataError):
    """token 失效——需要重新登录后重试。

    单独一类是因为**处理方式不同**：其它错误重试也没用，
    只有这个值得重新走一遍登录流程拿新 token。
    """


@dataclass(frozen=True)
class Device:
    """一台水表。

    Attributes:
        fm_address: 表地址（对应原 JS 的 fmAddress）。
        meter_id: 表号（对应原 JS 的 meterId）。
        device_code: 设备编号（对应原 JS 的 deviceCode），上报 MQTT 时用。
    """

    fm_address: str
    meter_id: str
    device_code: str


@dataclass(frozen=True)
class MeterRow:
    """表里的一行读数。

    Attributes:
        read_time: 读数时间（**原始值**，不转字符串）。
            接口实测返回的是毫秒时间戳（int），也见过日期字符串——
            保留原始类型，交给 time_utils.parse_read_time 去兼容，
            这里强行 str() 会让整点过滤失效。
        total_flux: 累计流量。
        raw: 该行的完整数据。
    """

    read_time: Any
    total_flux: float | None
    raw: dict[str, Any]


def build_query(
    device: Device,
    start_ms: int | None = None,
    end_ms: int | None = None,
) -> dict[str, str]:
    """构造查询参数。

    Args:
        device: 目标水表。
        start_ms: 起始毫秒时间戳，None 表示「昨天 0 点」。
        end_ms: 结束毫秒时间戳，None 表示「今天 23:59:59.999」。

    Returns:
        查询参数字典，值全部转成字符串（时间戳是 13 位，JS 里也是字符串）。

    默认区间取「昨天 0 点 → 今天结束」而不是「今天 0 点 → 现在」，
    因为水表读数是累计值：只查今天会丢掉昨天累积的那部分，
    报表上的「日用量」就全错了。
    """
    start = yesterday_start_millis() if start_ms is None else start_ms
    end = end_of_day_millis() if end_ms is None else end_ms

    return {
        "startDate": str(start),
        "endDate": str(end),
        "fmAddress": device.fm_address,
        "meterId": device.meter_id,
    }


def build_headers(token: str, user_id: str, user_name: str) -> dict[str, str]:
    """构造请求头。

    Args:
        token: 登录拿到的 JWT token。
        user_id: 用户 ID（取自登录响应的 data.userId）。
        user_name: 登录账号。

    Returns:
        请求头字典。

    Raises:
        MeterDataError: token 或 user_id 为空。
    """
    if not token:
        raise MeterDataError("取数需要 token：请先登录")
    if not user_id:
        raise MeterDataError(
            "取数需要 userId：登录响应里没拿到 data.userId，"
            "请在 .env 里配置 FUNENG_USER_ID 兜底"
        )

    return {
        "Content-Type": "application/json;charset=UTF-8",
        "Accept": "application/json, text/plain, */*",
        # 鉴权头：token 原样放进去（服务端认这个不带 Bearer 前缀）
        "Tw-Authorization": token,
        # Cookie 里也要带一份，原脚本就是这么写的——两个都带才拿得到数据
        "Cookie": (
            f"userId={user_id}; userName={user_name}; Tw-Authorization={token};"
        ),
        "User-Agent": _BROWSER_UA,
    }


def parse_rows(body: dict[str, Any]) -> list[MeterRow]:
    """把响应解析成读数列表。

    Args:
        body: 响应 JSON。

    Returns:
        读数列表（原始顺序，服务端按时间倒序返回）。

    Raises:
        MeterDataError: 响应结构不符合预期。
        TokenExpiredError: body 的 code 非 0（token 失效 / 参数不对）。
    """
    if "code" not in body:
        raise MeterDataError(f"取数响应缺少 code 字段：{body}")

    code = body.get("code")
    if code != CODE_SUCCESS:
        message = body.get("message", "")
        # 原脚本在这里判断 token 失效并重新登录。
        # 统一抛 TokenExpiredError，让调用方决定要不要重新登录。
        raise TokenExpiredError(
            f"取数失败：code={code} message={message!r}（token 可能已失效）"
        )

    data = body.get("data")
    if not isinstance(data, dict):
        raise MeterDataError(f"取数响应的 data 不是对象：{data!r}")

    table = data.get("table")
    if table is None:
        # 没有 table 字段 ≠ 报错，可能只是当天没数据。
        # 原脚本这里取 `data.data.table || []` 也是同样的容错。
        return []
    if not isinstance(table, list):
        raise MeterDataError(f"取数响应的 table 不是数组：{type(table).__name__}")

    rows: list[MeterRow] = []
    for item in table:
        if not isinstance(item, dict):
            continue
        rows.append(
            MeterRow(
                read_time=item.get("readTime"),
                total_flux=item.get("totalFlux"),
                raw=item,
            )
        )
    return rows


def fetch_meter_data(
    device: Device,
    token: str,
    user_id: str,
    user_name: str,
    session: Any | None = None,
    limit: int | None = None,
) -> list[MeterRow]:
    """拉一台水表的实时数据表。

    Args:
        device: 目标水表。
        token: 登录拿到的 JWT token。
        user_id: 用户 ID。
        user_name: 登录账号。
        session: 可复用的 requests.Session，None 表示新建一个。
        limit: 最多取多少条，None 表示全取（原 JS 是 33）。

    Returns:
        读数列表。

    Raises:
        MeterDataError: 请求失败或响应不是合法 JSON。
        TokenExpiredError: token 失效。
    """
    try:
        host_url = config.require_host_url()
    except config.ConfigError as e:
        raise MeterDataError(str(e)) from e

    url = f"{host_url}{METER_TABLE_PATH}"
    params = build_query(device)
    headers = build_headers(token, user_id, user_name)

    # 自建 session 时用 with 关闭；传进来的由调用方负责生命周期。
    if session is not None:
        resp = session.get(
            url, params=params, headers=headers, timeout=DATA_TIMEOUT
        )
    else:
        with net.new_session() as own:
            resp = own.get(
                url, params=params, headers=headers, timeout=DATA_TIMEOUT
            )

    try:
        body = resp.json()
    except ValueError as e:
        raise MeterDataError(
            f"取数接口返回的不是 JSON（HTTP {resp.status_code}）：{resp.text[:200]}"
        ) from e

    if not isinstance(body, dict):
        raise MeterDataError(f"取数接口返回的不是 JSON 对象：{body!r}")

    rows = parse_rows(body)
    if limit is not None:
        rows = rows[:limit]
    return rows


def fetch_all(
    token: str,
    user_id: str,
    user_name: str,
    devices: list[Device] | None = None,
    session: Any | None = None,
) -> dict[str, list[MeterRow]]:
    """拉所有设备的实时数据。

    Args:
        token: 登录拿到的 JWT token。
        user_id: 用户 ID。
        user_name: 登录账号。
        devices: 设备清单，None 表示用配置里的。
        session: 可复用的 requests.Session。

    Returns:
        {device_code: 读数列表}。

    Raises:
        MeterDataError: 设备清单没配置。
    """
    if devices is None:
        try:
            raw_devices = config.require_devices()
        except config.ConfigError as e:
            raise MeterDataError(str(e)) from e
        devices = [
            Device(
                fm_address=d["fmAddress"],
                meter_id=d["meterId"],
                device_code=d["deviceCode"],
            )
            for d in raw_devices
        ]

    result: dict[str, list[MeterRow]] = {}
    for device in devices:
        result[device.device_code] = fetch_meter_data(
            device, token, user_id, user_name, session=session
        )
    return result


def format_rows(rows: list[MeterRow]) -> str:
    """把读数列表格式化成可打印的文本。

    Args:
        rows: 读数列表。

    Returns:
        多行文本，每行一条读数。
    """
    if not rows:
        return "（无数据）"

    lines = []
    for row in rows:
        flux = row.total_flux
        flux_text = "-" if flux is None else f"{flux}"
        # readTime 是毫秒时间戳，直接打印看不出时间——用 time_utils 转成可读格式
        lines.append(f"{format_read_time(row.read_time)}  累计流量={flux_text}")
    return "\n".join(lines)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数。

    Args:
        argv: 参数列表，None 表示读 sys.argv。

    Returns:
        解析结果。``excel`` 为 None 表示不导出；
        为 DEFAULT_EXCEL_FLAG 表示导出到默认路径；否则是指定路径。
    """
    parser = argparse.ArgumentParser(
        prog="funeng_sync.meter_data",
        description="登录富能平台并拉取水表实时数据（可选导出 Excel）",
    )
    parser.add_argument(
        "--excel",
        nargs="?",
        const=DEFAULT_EXCEL_FLAG,
        default=None,
        metavar="路径",
        help=(
            "导出 Excel。省略路径则写到 out/水表数据_<时间戳>.xlsx。"
            "注意：表里含真实表号，out/ 已被 .gitignore 忽略。"
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """登录 -> 取数 -> 打印（可选导出 Excel）。

    用法：
        python -m funeng_sync.meter_data              # 只打印
        python -m funeng_sync.meter_data --excel      # 打印并导出到 out/
        python -m funeng_sync.meter_data --excel D:/x.xlsx   # 指定路径
    """
    # 延迟导入：login 依赖 ddddocr（需要 3.12 环境），放在模块顶层会让
    # 只用取数功能的人也被迫装 OCR 依赖。excel_export 同理——
    # openpyxl 是可选依赖，不该因为它没装就让整个模块 import 失败。
    from funeng_sync.login import LoginError, login

    args = _parse_args(argv)

    try:
        result = login()
    except LoginError as e:
        print(f"登录失败：{e}")
        return

    token = result.token or ""
    user_name = config.USER_NAME
    # userId 优先用登录响应里的——换账号时不用改代码。
    user_id = result.user_id or config.USER_ID

    print(f"登录成功，token 前 8 位：{token[:8]}…，userId={user_id}")

    try:
        device_meta = config.require_devices()
        devices = [
            Device(
                fm_address=d["fmAddress"],
                meter_id=d["meterId"],
                device_code=d["deviceCode"],
            )
            for d in device_meta
        ]
    except config.ConfigError as e:
        print(f"设备清单不可用：{e}")
        return

    # 共用一个 session：多台表连着查时能复用 TCP 连接。
    payload: dict[str, list[dict[str, Any]]] = {}
    with net.new_session() as session:
        for device in devices:
            print(f"\n===== 设备 {device.device_code} =====")
            try:
                rows = fetch_meter_data(
                    device, token, user_id, user_name, session=session
                )
            except TokenExpiredError as e:
                print(f"token 失效：{e}")
                print("请重新运行（会重新登录）")
                return
            except MeterDataError as e:
                print(f"取数失败：{e}")
                continue

            # 整点条数是下一阶段 MQTT 上报的候选量，先打出来对齐预期
            top_rows = [r for r in rows if is_top_of_hour(r.read_time)]
            print(
                f"共 {len(rows)} 条读数，其中整点 {len(top_rows)} 条"
                f"（上报时只取整点）"
            )
            print(format_rows(rows))

            # 导出要的是原始行（除 readTime/totalFlux 外还有正向/反向累计等），
            # 所以存 raw 而不是重新拼。
            payload[device.device_code] = [r.raw for r in rows]

    if args.excel is None:
        return

    # 延迟导入 excel_export：openpyxl 没装时也要能正常跑完取数打印，
    # 只在真的要导出时才报缺依赖。
    from funeng_sync.excel_export import (
        ExportError,
        default_output_path,
        export_to_excel,
    )

    if args.excel == DEFAULT_EXCEL_FLAG:
        out_path = default_output_path()
    else:
        out_path = Path(args.excel)
    try:
        saved = export_to_excel(payload, out_path, devices=device_meta)
    except ExportError as e:
        print(f"\n导出 Excel 失败：{e}")
        return

    print(f"\n已导出 Excel：{saved}")
    print("  汇总     —— 每台表一行：区间用量、条数、采样粒度、备注")
    print("  明细     —— 全部读数逐条，含本期用量差值，可筛选")
    print("  整点数据 —— 只留整点读数（MQTT 上报候选集）")
    print("  趋势     —— 时间 × 各表累计流量透视表 + 折线图")


if __name__ == "__main__":
    main()
