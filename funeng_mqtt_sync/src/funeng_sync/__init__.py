"""富能水表数据同步服务（Python 移植自 funeng_api_iemp/node/index.js）。

模块划分对应原 JS 的职责：
- config:         全局常量（host / topic / MQTT / 账号 / 设备列表 / 重试策略）
- time_utils:     dayjs 相关的时间处理（毫秒、起止日、整点判断）
- http_client:    下载验证码、阿里云 OCR、登录、拉取水表数据、构造 payload
- mqtt_client:    paho-mqtt 连接与发布
- sync:           编排（登录流程 + 取数发布 + 主循环倒计时）
- main:           入口
"""

__version__ = "0.1.0"
