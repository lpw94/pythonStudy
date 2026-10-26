"""从 celebrity-1000 数据集的 README 导出全量候选表。

为什么要有这个脚本
------------------
实测发现 CLIP 零样本认不出的名人，绝大多数**根本不在候选表里** ——
候选表就是模型的输出空间，人不在空间里，模型只能给个「像某个陌生人」的答案。

实测案例：Dwayne Johnson / Hugh Jackman / Mila Kunis 三人各 10 张图**全部**
识别失败（被认成 Jason Statham / Ben Affleck / Katy Perry）。
把三人加进候选表后，立刻全部正确识别（32% / 33% / 24%）。

所以候选表的**覆盖度**直接决定 CLIP 的天花板。手写 192 位显然不够，
而 celebrity-1000 数据集自带的 997 个名字正好覆盖了主流名人。

用法::

    E:/workBuddy/pythonStudy/.py312/python.exe scripts/export_dataset_candidates.py \
        --readme <celebrity-1000 的 README.md>

产物：``models/candidates.txt``（每行一个英文名，``load_candidates`` 自动加载）
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "models" / "candidates.txt"

# 名字里带分隔符的，用 | 之外的方式表达 —— 这里保留原样，
# 因为 CLIP 的文本塔认识 "Robert Downey Jr." 这种写法。
NAME_RE = re.compile(r"^\s*'(\d+)':\s*(.+?)\s*$", re.MULTILINE)


def main() -> int:
    """生成候选表。

    Returns:
        退出码。
    """
    parser = argparse.ArgumentParser(description="导出 celebrity-1000 全量候选表")
    parser.add_argument("--readme", required=True, help="数据集 README 路径")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="输出文件路径")
    args = parser.parse_args()

    text = Path(args.readme).read_text(encoding="utf-8")
    names = [name for _, name in NAME_RE.findall(text)]

    # 去重并保持顺序
    seen: set[str] = set()
    unique: list[str] = []
    for n in names:
        if n and n not in seen:
            seen.add(n)
            unique.append(n)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        "# 从 celebrity-1000 数据集导出的全量候选表（自动生成，勿手改）\n"
        "# 格式：英文名（CLIP 匹配用）。中文名请在 candidates_zh.txt 里补。\n"
        + "\n".join(unique)
        + "\n",
        encoding="utf-8",
    )

    print(f"已导出 {len(unique)} 位名人 → {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
