"""MQTT 客户端 —— 对应 index.js 里的 mqtt.connect / client.publish。

用 paho-mqtt 实现。connect 后启动后台网络循环（loop_start），
长连接模式下 publish 才不会丢包（对标 mqtt.js 的常驻连接）。
"""
import json
import logging

import paho.mqtt.client as mqtt

from .config import MQTT, TOPIC
from .http_client import build_payload

logger = logging.getLogger("funeng_sync")


def create_client() -> mqtt.Client:
    # paho 2.x 必须声明回调 API 版本
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2, client_id=MQTT["client_id"]
    )
    client.username_pw_set(MQTT["username"], MQTT["password"])

    def on_connect(_c, _userdata, _flags, _reason_code, _properties):
        logger.info("%s: 连接成功。。。。。", MQTT["host"])

    client.on_connect = on_connect

    try:
        # keepalive=60 对标 connectTimeout/长连接；reconnect 由 paho 自动处理
        client.connect(MQTT["host"], MQTT["port"], keepalive=60)
        client.loop_start()
    except Exception as e:  # noqa: BLE001
        logger.error("MQTT 连接失败: %s", e)
    return client


def publish(
    client: mqtt.Client,
    device_code: str,
    read_time_raw: str,
    total_flux,
) -> None:
    """对应 client.publish(topic, JSON.stringify(payload), { qos: 0 })。"""
    payload = build_payload(device_code, read_time_raw, total_flux)
    payload_str = json.dumps(payload, ensure_ascii=False)
    info = client.publish(TOPIC, payload_str, qos=0)
    if info.rc != mqtt.MQTT_ERR_SUCCESS:
        logger.error("发送错误 rc=%s", info.rc)
    else:
        logger.info(
            "%s 发送成功, 设备编号%s, 流量 %s",
            read_time_raw,
            device_code,
            total_flux,
        )
