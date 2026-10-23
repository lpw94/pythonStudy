"""富能水表数据同步服务（Python 移植自 funeng_api_iemp/node/index.js）。

模块划分对应原 JS 的职责：
- config:         全局常量（host / 账号 / 超时；敏感值走 .env）
- net:            HTTP 会话工厂（内网地址绕过企业代理）
- login:          登录换 token（POST /api/auth/jwt/token）
- login_test:     验证码下载 + 本地 OCR 识别（失败自动重试）
- time_utils:     dayjs 相关的时间处理（毫秒、起止日、整点判断）
- payload:        上报数据体构造（原 http_client.py 的一部分）
- mqtt_client:    paho-mqtt 连接与发布      ❌ 已裁剪
- sync:           编排（登录流程 + 取数发布 + 主循环倒计时）  ❌ 已裁剪
- main:           入口                        ❌ 已裁剪
"""

__version__ = "0.2.0"
