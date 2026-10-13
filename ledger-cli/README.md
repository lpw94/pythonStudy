# ledger-cli · 个人记账 CLI（Python 阶段 1 练习）

一个命令行记账工具：新增收支、列表、删除、汇总、按分类统计。
专为「有前端基础、想从项目学 Python」的同学设计——代码里到处是对照 JS 的注释。

## 技术栈
- **uv**：包管理器（对标 pnpm）——管 Python 版本 + 虚拟环境 + 依赖，一条命令搞定
- **Typer**：CLI 框架（装饰器即路由，对标 commander.js / yargs）
- **Rich**：终端美化输出
- **pytest**：测试（fixture 机制对标 Jest）
- **Ruff**：lint + format 一体（对标 ESLint + Prettier）

## 运行方式

```bash
cd ledger-cli

# 1) 安装依赖 + 创建虚拟环境（首次）
uv sync

# 2) 运行命令（uv run 会自动用项目里的 Python 环境）
uv run ledger add 38.5 餐饮 -t expense -n 午饭
uv run ledger add 8000 工资 -t income
uv run ledger list
uv run ledger summary
uv run ledger report
uv run ledger rm <ID>

# 也可以直接跑模块（无需 console 脚本）
uv run python -m ledger.main add 12.5 交通
```

> 数据默认存在**当前目录**的 `ledger.json`（已被 .gitignore 忽略），运行命令时所在的目录即数据目录。

## 测试

```bash
uv run pytest        # 跑全部测试
uv run pytest -q     # 安静模式
```

## 代码检查 / 格式化

```bash
uv run ruff check .  # lint
uv run ruff format . # 格式化
```

## 这个项目能帮你学到哪些 Python 语法
| 语法点 | 出现在 | 对标前端 |
|--------|--------|----------|
| 类型注解 `x: int = 1` | 全项目 | TypeScript 类型 |
| dataclass | models.py | interface + class 合并 |
| 列表推导 `[x for x in l if c]` | storage/service | arr.map / arr.filter |
| Enum 枚举 | models.py | TS enum / union |
| 生成器 `sum(x for ...)` | service.summary | arr.reduce |
| defaultdict | service.by_category | `acc[k] = (acc[k]\|\|0)+v` |
| pathlib 路径 | storage/main | path / fs 模块 |
| 模块导入 `from .x import` | 全部 | ES module import |
| 上下文 / 夹具 | tests/conftest | Jest beforeEach |
| 装饰器 `@app.command()` | main | 高阶函数 / 中间件注册 |

## 目录结构
```
ledger-cli/
├── pyproject.toml        # 依赖 + 工具配置（对标 package.json）
├── .gitignore
├── README.md
├── src/ledger/           # 包源码
│   ├── __init__.py
│   ├── models.py         # 数据模型（dataclass）
│   ├── storage.py        # JSON 持久化
│   ├── service.py        # 业务逻辑
│   └── main.py           # CLI 入口（Typer）
└── tests/                # pytest 测试
    ├── conftest.py
    └── test_service.py
```
