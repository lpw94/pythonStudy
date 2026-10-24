# funeng-mqtt-sync

把原 Node 脚本 `funeng_api_iemp/node/index.js` 移植成 Python：登录（验证码 OCR）→ 拉取水表小时数据 → 经 MQTT 上报。

## ⚠️ 当前状态：教学练手版（非完整同步脚本），取数阶段已完成

**登录 / 取数 / MQTT 上报的主体流程已在 `0d0dca6` 裁掉**，本项目现在是「项目驱动学 Python」阶段的**练手载体**，只保留了这些可以脱网验证的部分：

| 保留 | 说明 |
|------|------|
| `login.py` | **登录换 token**：拿验证码 -> 识别 -> 调 `/api/auth/jwt/token` |
| `meter_data.py` | **取数**：带 token 调 `meterRealTimeDataTable`，打印水表读数 |
| `captcha_demo.py` | 下载验证码 + ddddocr 离线识别（转发到 `login_test.py`，含失败重试） |
| `time_utils.py` | dayjs 等价的时间工具，纯函数，含毫秒时间戳解析 |
| `payload.py` | 上报数据体的构造，纯函数，锁住 `T_` 前缀这个易错点 |
| `demo_config.py` / `demo_import.py` / `demo_stdlib.py` | import 写法、标准库四件套的最小示例 |
| `supervision_demo.py` | 计算机视觉练手（轮廓检测 + 画框） |
| `config.py` | 配置结构；**所有敏感值走 `.env`，代码里不含真实地址、账号与表号** |

下面「与原 JS 的对应关系」及之后的部分保留了**完整版的移植记录**，作为阶段二的技术存档；其中 `mqtt_client.py` / `sync.py` / `main.py` 三个文件**目前并不存在**，要跑完整链路需先补回来。

当前可执行的检查：

```bash
.venv/Scripts/python.exe -m pytest tests -q                    # 90 passed
.venv/Scripts/python.exe -m ruff check src tests scripts        # All checks passed
.venv/Scripts/python.exe scripts/check_secrets.py              # 敏感信息自查
E:/workBuddy/pythonStudy/.py312/python.exe -m funeng_sync.login      # 只登录
E:/workBuddy/pythonStudy/.py312/python.exe -m funeng_sync.meter_data # 登录 + 取数打印
```

---

## 与原 JS 的对应关系（完整版存档）

| 原 JS | Python |
|------|--------|
| `axios` / `fetch` | `requests` |
| `mqtt` (mqtt.js) | `paho-mqtt` |
| `dayjs` | `datetime`（`time_utils.py`） |
| `fs` / `path` | `pathlib` |
| `setInterval` 倒计时 | `sync.run()` 里的 `while + time.sleep` |
| 全局变量 + `setTimeout` 递归 | `FunengSync` 类持有状态 |

## 目录结构

```
src/funeng_sync/
├── config.py           # 全局常量（host/账号/设备清单；敏感值全走 .env）✅ 保留
├── net.py              # HTTP 会话工厂（内网地址绕过企业代理）✅ 保留
├── login.py            # 登录换 token（POST /api/auth/jwt/token）✅ 保留
├── meter_data.py       # 取数（GET meterRealTimeDataTable）✅ 保留
├── time_utils.py       # 毫秒、起止日、整点判断（dayjs 等价）✅ 保留
├── payload.py          # 上报数据体构造 ✅ 保留（原来是 http_client.py 的一部分）
├── captcha_demo.py     # 验证码下载 + 识别（转发壳，实现见 login_test.py）✅ 保留
├── login_test.py       # 验证码下载 + 识别 + 失败重试（实现本体）✅ 保留
├── demo_config.py      # import 演示的被导入方
├── demo_import.py      # import 三种写法演示
├── demo_stdlib.py      # requests/json/datetime/pathlib 四件套演示
├── supervision_demo.py # 轮廓检测 + supervision 画框
├── mqtt_client.py      # ❌ 已删（paho 连接与发布）
├── sync.py             # ❌ 已删（登录流程 + 取数发布 + 主循环）
└── main.py             # ❌ 已删（入口）

scripts/check_ocr.py    # OCR 自检（只验证识别环节，不登录）
scripts/check_secrets.py # 敏感信息自查（扫工作区 + git 历史）
tests/                  # time_utils / payload / 验证码 / 登录 / 取数的单测，共 90 条
```

## 运行环境（重要）

默认走**本地离线识别**（`ddddocr`），它依赖 `opencv-python`，而 OpenCV
**在 Windows 上没有 Python 3.13 的预编译轮子**（3.11/3.12 才有）。
因此本项目用一个**免安装的 Python 3.12 环境**：`E:/workBuddy/pythonStudy/.py312`。

```bash
cd E:/workBuddy/pythonStudy/funeng_mqtt_sync

# 启动（推荐，双击也行）—— 跑一次登录流程
run.bat
# 或者显式调用
../.py312/python.exe -m funeng_sync.login
```

> 老的 `.venv`（3.13）仍保留，但**装不了 ddddocr**（OpenCV 没有 3.13 轮子）；
> 跑验证码识别请必须用 `.py312`。

## 运行（通用命令）

```bash
# 3.12 环境（本地 ddddocr 离线识别）
E:/workBuddy/pythonStudy/.py312/python.exe -m funeng_sync.login

# 依赖安装（首次）
E:/workBuddy/pythonStudy/.py312/python.exe -m pip install ddddocr requests
```

## 🔐 敏感配置处理

**这个仓库是公开的**，所以「服务地址 + 账号 + 密码」一律不进版本库。

### 原则：代码里不出现任何真实的生产配置

`config.py` 里这几项**没有默认值**：

| 配置项 | 内容 | 缺配置时的行为 |
|--------|------|----------------|
| `FUNENG_HOST_URL` | 生产服务端地址 | `require_host_url()` 抛 `ConfigError` |
| `FUNENG_USER_NAME` | 登录账号 | `require_user_name()` 抛 `ConfigError` |
| `FUNENG_PASSWORD_MD5` | 密码的 md5 | `require_password_md5()` 抛 `ConfigError` |
| `FUNENG_DEVICES` | 设备清单（真实表号） | `require_devices()` 抛 `ConfigError` |

> 刻意不写兜底默认值：宁可启动失败，也不要用一个硬编码的生产地址
> 把秘密重新带回版本库——**兜底默认值就是泄露的源头**。

读取优先级：**系统环境变量 > 项目根 `.env` > `config.py` 默认值**（仅限非敏感项）。

`FUNENG_USER_ID` 一般不用填——登录响应会返回 `data.userId`，取数时的 Cookie 头
直接用它；只有服务端不返回时才需要这个兜底项。

### 准备步骤

```bash
copy .env.example .env      # Windows
# cp .env.example .env      # macOS / Linux
```

然后填入真实值。密码填的是 **md5**，不是明文：

```bash
python -c "import hashlib;print(hashlib.md5(b'你的明文密码').hexdigest())"
```

设备清单（`FUNENG_DEVICES`）是一行 JSON 数组，真实表号同样不进版本库：

```
FUNENG_DEVICES=[{"fmAddress":"<表地址>","meterId":"<表号>","deviceCode":"<设备编号>"}]
```

### 提交前自查

```bash
.venv/Scripts/python.exe scripts/check_secrets.py
```

它做两件事：

1. **扫工作区** —— 用正则匹配内网 IP、32 位 md5、AK/SK、硬编码口令；
2. **扫 git 历史** —— 用 `git log -S` 反查每个真实值是否曾被提交过。

> **历史是最容易被忽略的泄露面**。`git rm` 只影响当前版本，
> 提交过的值在 `git log` 里永远还在——而且公开仓库的历史是可以被
> 任意 clone 下来逐个 commit 翻查的。

### 已做的处理

| 项 | 处理 |
|----|------|
| 密码 md5 | 从 `config.py` 移到 `.env`（`.env` 已在 `.gitignore`） |
| 百度 OCR AK/SK | 方案裁剪后**直接从 `.env` 删除**——没有使用场景却仍是可用凭据 |
| 内网地址 | `config.py` 改为纯 `.env` 驱动，无默认值 |
| 登录账号 | 同上 |
| 设备清单（真实表号） | 同上——`FUNENG_DEVICES` 一行 JSON，只在 `.env` 里 |
| demo 里的示例地址 | 换成 `10.0.0.1` 这类占位符（demo 本就该脱网） |
| 文档里的示例输出 | 全部改用占位符 |

## 登录换 token

用 3.12 环境跑（ddddocr 依赖 opencv，Windows 上没有 3.13 轮子）：

```bash
E:/workBuddy/pythonStudy/.py312/python.exe -m funeng_sync.login
```

流程与原 Node 脚本一致：**下载验证码 -> 本地识别 -> 带账号密码换 JWT token**。

```
下载验证码：http://<内网IP>:<端口>/api/auth/verificationCode/captcha-image/1792758014212 -> .../img
[1/5] 识别成功：czye  (.../img/captcha_1792758014212.jpg)
[1/5] 登录响应 code=0 message='SUCC'
登录成功
{
  "code": 0,
  "message": "SUCC",
  "data": { "token": "...", "name": "<你的账号>", "userId": 1990 }
}
```

请求体与原 JS 逐字对齐（`key` / `loginName` / `password` / `verificationCode`），
`password` 传的是**明文密码的 md5**。

### 坑 1：`key` 必须和验证码 URL 上的时间戳一致

验证码图片的地址是 `.../captcha-image/<毫秒时间戳>`，服务端拿这个时间戳
当本次验证码的唯一标识。登录时要把**同一个值**作为 `key` 传回去——
对不上就报「验证码错误」，哪怕验证码本身识别得完全正确。

所以 `download_captcha()` 返回 `(图片路径, key)`，`download_and_recognize()`
返回 `Captcha(path, key, code)`，`key` 一路带到请求体里。

顺带一提：早前把时间戳写成 `?t=xxx` 查询参数形式（URL 结尾多个斜杠），
服务端返回的是 **44 字节的 JSON 错误**而不是图片。现在统一走
`build_captcha_url()` 拼路径段。

### 坑 2：HTTP 200 不代表登录成功

服务端**所有分支都返回 HTTP 200**，成败只看 body 里的 `code`：

| 场景 | 返回 |
|------|------|
| 成功 | `{"code":0,"message":"SUCC","data":{"token":...,"name":...,"userId":1990}}` |
| 验证码错（含 key 对不上） | `{"code":-1,"message":"验证码错误","data":null}` |
| 验证码为空 | `{"code":-1,"message":"验证码无效","data":null}` |
| 账号密码错 | `{"code":-1,"message":"用户名或密码错误","data":null}` |

所以不能用 `resp.ok` 判断，必须解析 JSON 看 `code`。

### 坑 3：只有「验证码错误」才值得重试

识别难免出错（把 `5` 认成 `b` 这类），所以「验证码错误」会重新下载一张图再试，
最多 `MAX_LOGIN_RETRY`（默认 5）次，每次间隔 `RETRY_INTERVAL`（默认 10 秒，
与原 JS 一致）。

但**账号密码错误直接抛错，不重试**——重试不会变对，只会反复撞服务端的
失败次数限制。

### 坑 4：内网地址必须绕过企业代理

本机设了 `http_proxy`，`requests` 会自动读环境变量代理。而内网地址
是直连的，走代理时实测会拿到：

- **0 字节**（连接被代理吞掉，`requests` 还不报错，只是空响应）
- **44 字节的 JSON**（`{"code":20000,"message":"Token不能为空"}`）

`net.new_session()` 统一用 `session.trust_env = False` 绕开。
需要访问外网域名时再用 `proxies=` 显式指定。

## 验证码下载与识别

用 3.12 环境跑（ddddocr 依赖 opencv，Windows 上没有 3.13 轮子）：

```bash
E:/workBuddy/pythonStudy/.py312/python.exe -m funeng_sync.login_test          # 下载 + 识别（失败自动重试）
E:/workBuddy/pythonStudy/.py312/python.exe -m funeng_sync.login_test img/a.jpg # 只识别指定图片
E:/workBuddy/pythonStudy/.py312/python.exe -m funeng_sync.captcha_demo        # 同上，兼容入口
```

`captcha_demo.py` 是 `login_test.py` 的转发壳，实现只有一份。

### 识别失败会自动重试

验证码固定 **4 位**（`CAPTCHA_LENGTH`）。识别结果长度不对就判定为识别失败
（多认一个字、少认一个字，或把干扰线认成了字符），**重新下载一张新图再识别**，
最多 `MAX_RETRY`（默认 5）次：

```
[1/5] 识别结果长度 3 != 4，判定为识别失败：'ab1'  重新下载再试
[2/5] 识别成功：Ptq5  (img/captcha_1792758014212.jpg)
```

### 一个坑：服务端返回 JSON 错误时会被当成图片

验证码接口在 Token 失效等情况下会返回 **HTTP 200 + JSON 错误**：

```json
{"code":20000,"message":"Token不能为空"}
```

早期版本不校验内容就直接存成 `.jpg`，后果是 ddddocr 报
`cannot identify image file` —— **报错信息完全指不到真正的原因**。
现在下载阶段会先按图片魔数（`\xff\xd8\xff` / `\x89PNG` / `GIF8` / `BM` / `RIFF`）校验，
不是图片就抛 `CaptchaError`，并把服务端的错误信息带出来。

### 换识别方案

当前只保留**本地离线 ddddocr** 一种方案：它专为验证码训练，无需联网、无需 AK/SK。
云端 `baidu` 方案随 `http_client.py` 一起裁剪掉了（见下方「已删文件」）。

实测 ddddocr 对现有验证码样本全部输出 4 位（人工核对约 3/4 完全正确，
个别把数字 `5` 误读成字母 `b`）；配合「识别失败重试」，成功率足够。

## 取数（登录 → 拉水表读数）

用 3.12 环境跑（依赖 ddddocr）：

```bash
E:/workBuddy/pythonStudy/.py312/python.exe -m funeng_sync.meter_data
```

实测输出：

```
[1/5] 识别成功：Nyjw  (.../img/captcha_1792825395306.jpg)
[1/5] 登录响应 code=0 message='SUCC'
登录成功，token 前 8 位：CB5451FD…，userId=1990

===== 设备 XT001 =====
共 129 条读数，其中整点 33 条（上报时只取整点）
2026-10-24 08:00:00  累计流量=438826.66
2026-10-24 07:45:00  累计流量=438824.34
2026-10-24 07:30:00  累计流量=438821.9
...
```

接口是 `GET /api/largeCustomer/operationManagement/meterRealTimeDataTable`，
请求参数与原 JS 逐字对齐：`startDate` / `endDate` / `fmAddress` / `meterId`。

### 坑 1：鉴权要带**两个**地方

```python
headers = {
    "Tw-Authorization": token,          # 请求头
    "Cookie": f"userId={user_id}; userName={user_name}; Tw-Authorization={token};",
}
```

token 要同时放进 `Tw-Authorization` 请求头**和** `Cookie` 头里——原脚本两个都带，
只带一个拿不到数据。`userId` 用**登录响应里的 `data.userId`**（本项目实测返回 `1990`），
不在代码里写死，换账号时不用改代码。

### 坑 2：时间区间是毫秒时间戳，且默认跨天

`startDate` / `endDate` 传的是**毫秒时间戳字符串**，不是日期字符串。
默认取「昨天 0 点 → 今天 23:59:59.999」，因为水表读数是**累计值**：
只查今天会丢掉昨天累积的那部分，报表上的「日用量」就全错了。

### 坑 3：`readTime` 是毫秒时间戳，不是日期字符串

这是本阶段最容易翻车的一个坑。

原 JS 写的是 `dayjs(readTime).minute() === 0`——**dayjs 接受数字毫秒时间戳**。
而 Python 侧若只按 ISO 字符串解析（`datetime.fromisoformat`），
会走到 `except` 分支返回 `False`，结果是：

> **整点过滤全军覆没，一条都不上报，而且不报错。**

实测接口返回的 `readTime` 就是 `1792800000000` 这种数字。
现在 `time_utils.parse_read_time` 三种形态都认：毫秒时间戳（int / 数字字符串）、
`"2026-10-13 00:00:00"`、带 `Z` 的 ISO 8601。

修复前后对比（同一批数据）：

| | 整点命中 |
|---|---|
| 修复前（只按 ISO 解析） | **0 / 129** |
| 修复后（认毫秒时间戳） | **33 / 129** |

33 条正好对应原 JS 里 `slice(0, 33)` 的设计意图——一天多的整点数据。

### 坑 4：HTTP 200 不代表取数成功

和登录接口一样，服务端所有分支都返回 HTTP 200，业务码在 body 的 `code` 里。
`code` 非 0 → `TokenExpiredError`（token 失效），与其它错误区分开——
只有这一类值得重新登录后重试。

### 坑 5：接口会拒绝 python-requests 的默认 UA

取数请求带浏览器 UA（`_BROWSER_UA`），与原脚本的 session 设置一致。

## 行为要点（与原脚本一致）

- 启动 10 秒后首次登录；之后每 480 分钟（8 小时）一次。
- 登录失败最多 5 次，达到上限后暂停 2 小时再试。
- 多设备取数按 `index * 2s` 错峰（delayedLog）。
- 只对「整点」(`minute === 0`) 的数据点发布到 MQTT。
- 取数返回 token 失效时，3 秒后自动重新登录。

## 阶段小结

| 已完成 | 状态 |
|--------|------|
| 验证码下载 + 离线识别 | ✅ 含失败自动重试、图片魔数校验 |
| 登录换 token | ✅ 含 key 绑定、错误分支判定、分类重试 |
| 取数（meterRealTimeDataTable） | ✅ 含双处鉴权、毫秒时间戳解析、整点统计 |
| 敏感配置外置 | ✅ 地址/账号/密码/表号全走 `.env`，附自查脚本 |
| 单元测试 | ✅ 90 条 |
| 代码质量 | ✅ ruff 全绿 |

**未做**（属于下一阶段）：MQTT 发布、错峰调度、8 小时主循环。
