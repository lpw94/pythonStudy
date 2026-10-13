# 阶段2 能源数据导入 ETL（energy-etl）

> 阶段 2 脚本自动化练习：把大屏项目里的 `hourlyData.js` / `yearData.js`（四类能源 Excel 定时导入）用 Python 重写。
> 技术栈：`pandas` + `openpyxl` + `httpx` + `schedule` + `pydantic-settings` + `typer`。

## 它解决什么问题

大屏后端有一组 Node 脚本，定期把**四类能源**（电量 / 水量 / 天然气 / 热力）的月度 Excel 数据导入，
并按 `scopeType` 区分 **park（园区）/ product（产品）** 维度聚合。本脚手架用 Python 复刻它的骨架：
取数 → 读 Excel → 清洗聚合 → 输出（真实场景改为写库/推接口）。

## 目录结构

```
energy-etl/
├── pyproject.toml        # 依赖 + 工具配置（对标 package.json）
├── README.md
├── data/
│   └── sample_energy.xlsx # 示例数据（scripts/make_sample.py 生成）
├── scripts/
│   └── make_sample.py     # 生成示例 Excel
├── src/energy_etl/
│   ├── models.py          # EnergyType 枚举 + EnergyRecord（对标 TS interface）
│   ├── config.py          # pydantic-settings 配置（Excel 路径/远程URL/定时）
│   ├── excel_reader.py    # pandas 读 Excel
│   ├── transformer.py     # pandas 聚合（按园区汇总）
│   ├── fetcher.py         # httpx 取数（脚手架默认读本地）
│   ├── pipeline.py        # 编排：取数→读→聚合→输出
│   ├── scheduler.py       # schedule 早/晚定时（对标 scheduleMorning/Afternoon）
│   └── main.py            # Typer CLI（run 单次 / serve 持续）
└── tests/                 # pytest（conftest 造数据 + 转换层测试）
```

## 快速开始

```bash
cd E:/workBuddy/pythonStudy/energy-etl
# 1. 创建 venv + 装依赖（首次）
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e .

# 2. 生成示例 Excel
.venv/Scripts/python.exe scripts/make_sample.py

# 3. 单次运行（读取 → 聚合 → 打印）
.venv/Scripts/energy-etl.exe run
#   或指定文件：energy-etl run -p data/sample_energy.xlsx

# 4. 持续调度（早 08:00 / 晚 20:00 各跑一次，Ctrl+C 退出）
.venv/Scripts/energy-etl.exe serve
```

## 测试 & 代码检查

```bash
.venv/Scripts/python.exe -m pytest tests -q
.venv/Scripts/ruff.exe check src
```

## 如何替换成你真实的大屏逻辑

把 `hourlyData.js` / `yearData.js` 的路径或内容给我后，主要改这三处：

1. **`excel_reader.py`** — 对齐你 Excel 的真实列名 / Sheet 名 / 表头位置。
2. **`fetcher.py`** — 把 `remote_url` 指向真实接口，或改成读你现有的数据源。
3. **`pipeline.py` 的输出步** — 把 `console.print` 换成写数据库 / 调你的落库接口；`product` 维度可在 `models.EnergyRecord` 加 `organization` 字段并扩展 `transformer.aggregate_by_park`。

> 配置项（Excel 路径、远程地址、定时时间）都通过环境变量覆盖，前缀 `ENERGY_`，
> 例如 `ENERGY_MORNING_AT=09:30 energy-etl serve`。
