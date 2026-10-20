"""payload 构造 —— 对应 index.js 里 getData 的 obj / payload 结构。

阶段二裁剪时随网络请求逻辑一起移除了，这里只保留**纯函数**部分：
请求发起、鉴权、MQTT 上报都不在范围内（那属于阶段三之后的扩展）。

为什么要单独留一个文件：`build_payload` 是唯一"能脱网验证"的数据契约——
它决定了往服务端推的 JSON 长什么样，写错了后端会静默丢数据。
把它独立出来才能用单测锁住。
"""
from __future__ import annotations


def build_payload(
    device_code: str, read_time_raw: str, total_flux: float
) -> list[dict]:
    """构造 getData 用的 payload。

    对应 index.js 里这段::

        const obj = { deviceCode };
        obj[`T_${readTime}`] = { datas: { internetTraffic: totalFlux } };
        const payload = [obj];

    注意 ``T_`` 这个前缀不是笔误，服务端就是按这个 key 解析时间点的，
    少写一个字符后端会当无效数据丢掉，而且不报错——最难查的那种坑。

    返回单元素列表而非对象本身，是因为接口的 body 就是一个数组。
    """
    obj: dict = {"deviceCode": device_code}
    obj[f"T_{read_time_raw}"] = {"datas": {"internetTraffic": total_flux}}
    return [obj]