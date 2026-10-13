"""配置层：用 pydantic-settings 管理运行参数（对标 dotenv + 强类型）。

环境变量前缀 ENERGY_，例如 ENERGY_EXCEL_PATH=xxx.xlsx 会覆盖默认值。
真实接入大屏时，把 remote_url / 定时时间改成你的接口与排期即可。
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ENERGY_")

    # 本地示例 Excel 路径（脚手架默认）
    excel_path: Path = Path("data/sample_energy.xlsx")

    # 真实场景：远程 Excel / 数据接口地址（fetcher 使用）
    remote_url: str = ""

    # 定时配置（对标 hourlyData 的 scheduleMorning / scheduleAfternoon）
    morning_at: str = "08:00"
    afternoon_at: str = "20:00"


settings = Settings()
