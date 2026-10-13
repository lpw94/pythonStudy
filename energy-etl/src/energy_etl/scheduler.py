"""调度层：用 schedule 实现早/晚定时任务。

对标 hourlyData.js 里的 scheduleMorning / scheduleAfternoon：
  早上 08:00 跑一次、晚上 20:00 跑一次，循环等待触发。
"""
from __future__ import annotations

import time

import schedule

from .config import settings
from .pipeline import run_pipeline


def morning_job() -> None:
    print(f"[scheduler] 早间任务 {settings.morning_at} 触发")
    run_pipeline()


def afternoon_job() -> None:
    print(f"[scheduler] 晚间任务 {settings.afternoon_at} 触发")
    run_pipeline()


def start() -> None:
    """注册定时任务并进入阻塞循环（Ctrl+C 退出）。"""
    schedule.every().day.at(settings.morning_at).do(morning_job)
    schedule.every().day.at(settings.afternoon_at).do(afternoon_job)
    print("[scheduler] 已启动，按 Ctrl+C 退出")
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[scheduler] 已停止")
