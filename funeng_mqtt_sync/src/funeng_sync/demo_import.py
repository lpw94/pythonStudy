"""示例：如何引用「另一个文件」里的变量（Python 导入三种写法）。

运行（从项目根目录）:
    E:/workBuddy/pythonStudy/.py312/python.exe -m funeng_sync.demo_import

知识点：
1. import 模块              -> 通过「模块名.变量」访问（推荐，改值全局生效）
2. from 模块 import 变量     -> 直接拿名字到当前命名空间（省前缀）
3. 包内相对导入 from . import -> 等价写法 2，但只能用 python -m 跑，不能 python xxx.py
4. 不可变 / 可变对象在两种写法下的行为差异
"""

from __future__ import annotations

# 写法 1：import 整个模块，用「模块名.变量」访问
# 好处：所有来源都带前缀，可读性强；改 cfg.xxx 会作用回源模块
import funeng_sync.demo_config as cfg

# 写法 2：from ... import ... 直接把名字拿进当前命名空间
from funeng_sync.demo_config import APP_NAME, build_url

# 写法 3：包内相对导入（等价写法 2，但只能在包内使用）
from .demo_config import TIMEOUT


def main() -> None:
    """演示三种写法，并对比可变 / 不可变对象在导入后的差异。"""
    # --- 写法 1：通过模块对象访问 ---
    print("[1] import 模块:")
    print("    cfg.BASE_URL          =", cfg.BASE_URL)
    print("    cfg.build_url('/api') =", cfg.build_url("/api"))

    # --- 写法 2：直接用名字 ---
    print("[2] from import 直接拿名字:")
    print("    APP_NAME              =", APP_NAME)
    print("    build_url('/api/y')   =", build_url("/api/y"))

    # --- 写法 3：相对导入拿到的名字 ---
    print("[3] 相对导入:")
    print("    TIMEOUT               =", TIMEOUT)

    # --- 坑：不可变 vs 可变 ---
    print("[4] 可变 / 不可变差异:")
    # 不可变：重新赋值只是覆盖「本地名字」，不影响源模块
    local_name = APP_NAME
    local_name = "改了本地"
    print("    本地改 APP_NAME 后，源模块仍是:", cfg.APP_NAME)

    # 可变：list.append 作用到同一对象，源模块也跟着变
    cfg.ALLOWED_CODES.append("new")
    print("    通过 cfg 改 ALLOWED_CODES 后:", cfg.ALLOWED_CODES)


if __name__ == "__main__":
    # 这个守卫让模块既能当脚本跑（python -m），被 import 时又不会自动执行
    main()
