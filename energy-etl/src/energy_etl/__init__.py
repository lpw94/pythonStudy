"""阶段2 能源 ETL 包：把大屏的四类能源 Excel 导入脚本用 Python 重写。

对标前端项目里的 hourlyData.js / yearData.js：
  - 电量 / 水量 / 天然气 / 热力 四类能源
  - 月度 Excel 数据
  - 早/晚定时导入（scopeType 区分 park / product 维度）
"""
