"""入口 —— 对应 index.js 作为脚本直接运行。

用法：
    funeng-sync          # 安装后可执行
    python -m funeng_sync.main
"""
import logging

from .sync import FunengSync


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    sync = FunengSync()
    try:
        sync.run()
    except KeyboardInterrupt:
        logging.info("已停止")


if __name__ == "__main__":
    main()
