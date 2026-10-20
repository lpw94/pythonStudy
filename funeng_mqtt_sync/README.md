# funeng-mqtt-sync

把原 Node 脚本 `funeng_api_iemp/node/index.js` 移植成 Python：登录（验证码 OCR）→ 拉取水表小时数据 → 经 MQTT 上报。

## ⚠️ 当前状态：教学练手版（非完整同步脚本）

**登录 / 取数 / MQTT 上报的主体流程已在 `0d0dca6` 裁掉**，本项目现在是「项目驱动学Python」阶段二的**练手载体**，只保留了这些可以脱网验证的部分：

| 保留 | 说明 |
|------|------|
| `captcha_demo.py` | 下载验证码 + ddddocr 离线识别（不断生产网络也能看效果） |
| `time_utils.py` | dayjs 等价的时间工具，纯函数，9 条单测覆盖 |
| `payload.py` | 上报数据体的构造，纯函数，锁住 `T_` 前缀这个易错点 |
| `demo_config.py` / `demo_import.py` / `demo_stdlib.py` | import 写法、标准库四件套的最小示例 |
| `supervision_demo.py` | 计算机视觉练手（轮廓检测 + 画框） |
| `config.py` | 配置结构与生产常量（**含敏感信息，勿外传**） |

下面「与原 JS 的对应关系」及之后的部分保留了**完整版的移植记录**，作为阶段二的技术存档；其中 `http_client.py` / `mqtt_client.py` / `sync.py` / `main.py` 四个文件**目前并不存在**，要跑完整链路需先补回来。

当前可执行的检查：

```bash
.venv/Scripts/python.exe -m pytest tests -q                    # 9 passed
.venv/Scripts/python.exe -m ruff check src scripts tests       # All checks passed
E:/workBuddy/pythonStudy/.py312/python.exe -m funeng_sync.demo_import
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
├── config.py           # 全局常量（host/topic/MQTT/账号/设备列表/OCR/重试策略）
├── time_utils.py       # 毫秒、起止日、整点判断（dayjs 等价）✅ 保留
├── payload.py          # 上报数据体构造 ✅ 保留（原来是 http_client.py 的一部分）
├── captcha_demo.py     # 验证码下载 + ddddocr 识别 ✅ 保留
├── demo_config.py      # import 演示的被导入方
├── demo_import.py      # import 三种写法演示
├── demo_stdlib.py      # requests/json/datetime/pathlib 四件套演示
├── supervision_demo.py # 轮廓检测 + supervision 画框
├── mqtt_client.py      # ❌ 已删（paho 连接与发布）
├── sync.py             # ❌ 已删（登录流程 + 取数发布 + 主循环）
└── main.py             # ❌ 已删（入口）

scripts/check_ocr.py    # OCR 自检（单独验证验证码识别环节）
tests/                  # time_utils 与 payload 的单测，共 9 条
```

## 运行环境（重要）

默认走**本地离线识别**（`ddddocr`），它依赖 `opencv-python`，而 OpenCV
**在 Windows 上没有 Python 3.13 的预编译轮子**（3.11/3.12 才有）。
因此本项目用一个**免安装的 Python 3.12 环境**：`E:/workBuddy/pythonStudy/.py312`。

```bash
cd E:/workBuddy/pythonStudy/funeng_mqtt_sync

# 启动（推荐，双击也行）
run.bat
# 或者显式调用
../.py312/python.exe -m funeng_sync.main
```

> 老的 `.venv`（3.13）仍保留，只能跑 `OCR_PROVIDER="baidu"` 的在线方案；
> 跑 `ddddocr` 请必须用 `.py312`。

## 运行（通用命令）

```bash
# 3.12 环境（支持 ddddocr + baidu 两种识别）
E:/workBuddy/pythonStudy/.py312/python.exe -m funeng_sync.main

# 依赖安装（首次）
E:/workBuddy/pythonStudy/.py312/python.exe -m pip install ddddocr requests paho-mqtt
```

## 验证（不触达生产网络）

```bash
E:/workBuddy/pythonStudy/.py312/python.exe -m pytest tests -q   # 或 .venv/Scripts/python.exe
.venv/Scripts/ruff.exe check src scripts
```

## 验证码识别自检

单独验证「识别」这一环，不登录、不连 MQTT：

```bash
E:/workBuddy/pythonStudy/.py312/python.exe scripts/check_ocr.py          # img/ 最新一张
E:/workBuddy/pythonStudy/.py312/python.exe scripts/check_ocr.py 图.jpg   # 指定图片
```

用百度方案时，输出会先告诉你 AK/SK 能不能换到 token，再告诉你 OCR 接口有没有权限。

### 常见错误：`error_code=6 No permission to access data`

含义是「应用没有该接口的权限」，**不是** 识别不准，也不是 AK/SK 无效
（AK/SK 无效会在换 token 那一步就失败）。按顺序排查：

1. 进百度智能云控制台 → **文字识别 OCR** → 应用列表 → 新建/编辑应用，
   在接口权限里勾选 **通用文字识别**。
2. 用**这个 OCR 应用**的 API Key / Secret Key 填到 `config.py`
   （在其他产品如「图像识别」「千帆大模型」下创建的应用，AK/SK 不通用）。
3. 控制台「概览」页确认已领取通用文字识别的免费额度（通常 1000 次/月）。
4. 改完重启程序（token 有 25 天缓存，重启会重新换取）。

### 换识别方案

`config.py` 里两个开关，**两种方案都保留**，改一行即可切换：

| 配置 | 可选值 | 说明 |
|------|--------|------|
| `OCR_PROVIDER` | `ddddocr`（默认）/ `baidu` | `ddddocr` 本地离线识别，专为验证码训练，无需联网和 AK/SK；`baidu` 走云端在线识别 |
| `BAIDU_OCR_ENDPOINT` | `general_basic` / `accurate_basic` | 仅 `baidu` 方案生效，高精度版对小图识别率通常更好 |

实测 ddddocr 对现有 5 张验证码样本全部输出 4 位（人工核对约 3/4 完全正确，
个别把数字 `5` 误读成字母 `b`）；配合登录流程的 5 次重试，成功率足够。

## ⚠️ 安全提示

`config.py` 里包含生产环境地址、登录账号、密码（md5）和百度 OCR 的 API Key / Secret Key。
本移植 1:1 照搬原 JS 以便直接运行；正式部署请改为从环境变量读取（参考 `.env.example`），
并确保 `config.py` / `.env` 不被提交到 git。

## 行为要点（与原脚本一致）

- 启动 10 秒后首次登录；之后每 480 分钟（8 小时）一次。
- 登录失败最多 5 次，达到上限后暂停 2 小时再试。
- 多设备取数按 `index * 2s` 错峰（delayedLog）。
- 只对「整点」(`minute === 0`) 的数据点发布到 MQTT。
- 取数返回 token 失效时，3 秒后自动重新登录。
