# funeng-mqtt-sync

把原 Node 脚本 `funeng_api_iemp/node/index.js` 移植成 Python：登录（验证码 OCR）→ 拉取水表小时数据 → 经 MQTT 上报。

## ⚠️ 当前状态：教学练手版（非完整同步脚本）

**登录 / 取数 / MQTT 上报的主体流程已在 `0d0dca6` 裁掉**，本项目现在是「项目驱动学Python」阶段二的**练手载体**，只保留了这些可以脱网验证的部分：

| 保留 | 说明 |
|------|------|
| `login.py` | **登录换 token**：拿验证码 -> 识别 -> 调 `/api/auth/jwt/token` |
| `captcha_demo.py` | 下载验证码 + ddddocr 离线识别（转发到 `login_test.py`，含失败重试） |
| `time_utils.py` | dayjs 等价的时间工具，纯函数，9 条单测覆盖 |
| `payload.py` | 上报数据体的构造，纯函数，锁住 `T_` 前缀这个易错点 |
| `demo_config.py` / `demo_import.py` / `demo_stdlib.py` | import 写法、标准库四件套的最小示例 |
| `supervision_demo.py` | 计算机视觉练手（轮廓检测 + 画框） |
| `config.py` | 配置结构与生产常量（敏感值走 `.env`，**勿外传**） |

下面「与原 JS 的对应关系」及之后的部分保留了**完整版的移植记录**，作为阶段二的技术存档；其中 `http_client.py` / `mqtt_client.py` / `sync.py` / `main.py` 四个文件**目前并不存在**，要跑完整链路需先补回来。

当前可执行的检查：

```bash
.venv/Scripts/python.exe -m pytest tests -q                    # 47 passed
.venv/Scripts/python.exe -m ruff check src tests               # All checks passed
E:/workBuddy/pythonStudy/.py312/python.exe -m funeng_sync.login
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
├── config.py           # 全局常量（host/账号/超时；敏感值走 .env）✅ 保留
├── net.py              # HTTP 会话工厂（内网地址绕过企业代理）✅ 保留
├── login.py            # 登录换 token（POST /api/auth/jwt/token）✅ 保留
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

scripts/check_ocr.py    # ❌ 已失效（依赖已删的 http_client，改用 login_test.py）
tests/                  # time_utils / payload / 验证码 / 登录的单测，共 47 条
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

## 验证（不触达生产网络）

```bash
.venv/Scripts/python.exe -m pytest tests -q                    # 47 passed
.venv/Scripts/python.exe -m ruff check src tests
```

## 登录换 token

用 3.12 环境跑（ddddocr 依赖 opencv，Windows 上没有 3.13 轮子）：

```bash
E:/workBuddy/pythonStudy/.py312/python.exe -m funeng_sync.login
```

流程与原 Node 脚本一致：**下载验证码 -> 本地识别 -> 带账号密码换 JWT token**。

```
下载验证码：http://10.0.0.1:8080/api/auth/verificationCode/captcha-image/1792758014212 -> .../img
[1/5] 识别成功：czye  (.../img/captcha_1792758014212.jpg)
[1/5] 登录响应 code=0 message='SUCC'
登录成功
{
  "code": 0,
  "message": "SUCC",
  "data": { "token": "...", "name": "your_account", "userId": 1990 }
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

本机设了 `http_proxy`，`requests` 会自动读环境变量代理。而
`10.0.0.1` 是内网直连地址，走代理时实测会拿到：

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

## ⚠️ 安全提示

密码 md5 **不写在 `config.py` 里**，而是从项目根目录的 `.env` 读取
（`FUNENG_PASSWORD_MD5`），`.env` 已在 `.gitignore` 中，不会被提交。
读取优先级：系统环境变量 > `.env` > `config.py` 里的默认值。

`config.py` 里仍有生产环境地址和登录账号，属于半敏感信息，**勿外传**。

## 行为要点（与原脚本一致）

- 启动 10 秒后首次登录；之后每 480 分钟（8 小时）一次。
- 登录失败最多 5 次，达到上限后暂停 2 小时再试。
- 多设备取数按 `index * 2s` 错峰（delayedLog）。
- 只对「整点」(`minute === 0`) 的数据点发布到 MQTT。
- 取数返回 token 失效时，3 秒后自动重新登录。
