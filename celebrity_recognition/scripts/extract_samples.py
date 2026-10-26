"""从 celebrity-1000 数据集导出测试素材。

数据集：``tonyassi/celebrity-1000``（hf-mirror 上可下载）
内容：997 位名人的 18184 张图，每人约 20 张。

用途
----
1. 拿真实名人的脸验证 CLIP 零样本的准确率；
2. 顺便当**人脸特征库的参考图**素材 —— 建库流程的测试数据。

不是运行必需：这个脚本只是准备测试数据，识别功能本身不依赖它。

运行::

    E:/workBuddy/pythonStudy/.py312/python.exe scripts/extract_samples.py \
        --parquet <路径> --readme <路径> --out img/celebrity_samples
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pyarrow.parquet as pq

# 想要的测试对象：名字（README 里的原始拼写）-> 输出的目录名
WANTED = {
    "Tom Cruise": "Tom Cruise",
    "Leonardo DiCaprio": "Leonardo DiCaprio",
    "Brad Pitt": "Brad Pitt",
    "Matt Damon": "Matt Damon",
    "Emma Watson": "Emma Watson",
    "Scarlett Johansson": "Scarlett Johansson",
    "Taylor Swift": "Taylor Swift",
    "Adele": "Adele",
    "Lionel Messi": "Lionel Messi",
    "Cristiano Ronaldo": "Cristiano Ronaldo",
    "Kobe Bryant": "Kobe Bryant",
    "LeBron James": "LeBron James",
    "Jackie Chan": "Jackie Chan",
    "Hugh Jackman": "Hugh Jackman",
    "Robert Downey Jr.": "Robert Downey Jr.",
    "Mila Kunis": "Mila Kunis",
    "Jennifer Lawrence": "Jennifer Lawrence",
    "Anne Hathaway": "Anne Hathaway",
    "Dwayne Johnson": "Dwayne Johnson",
}


def parse_names(readme_path: Path) -> dict[int, str]:
    """从数据集 README 里解析 label 索引到人名的映射。

    README 的格式是 YAML front matter::

        names:
          '0': Aaron Eckhart

    Args:
        readme_path: README 路径。

    Returns:
        {label_index: name} 字典。
    """
    text = readme_path.read_text(encoding="utf-8")
    names: dict[int, str] = {}
    for idx, name in re.findall(r"'(\d+)':\s*(.+)", text):
        names[int(idx)] = name.strip()
    return names


def main() -> int:
    """导出指定名人的图片。

    Returns:
        退出码。
    """
    parser = argparse.ArgumentParser(description="导出 celebrity-1000 的样本图")
    parser.add_argument("--parquet", required=True, help="parquet 文件路径")
    parser.add_argument("--readme", required=True, help="数据集 README 路径")
    parser.add_argument("--out", required=True, help="输出目录")
    parser.add_argument("--per-person", type=int, default=5, help="每人导出几张")
    args = parser.parse_args()

    names = parse_names(Path(args.readme))
    wanted_labels: dict[int, str] = {}
    for label, name in names.items():
        if name in WANTED:
            wanted_labels[label] = name

    found = {n for n in names.values()}
    missing = [w for w in WANTED if w not in found]
    if missing:
        print(f"数据集里没有这些人（跳过）：{missing}")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    pf = pq.ParquetFile(args.parquet)
    exported: dict[str, int] = {}

    for rg in range(pf.num_row_groups):
        table = pf.read_row_group(rg, columns=["image", "label"])
        labels = table.column("label").to_pylist()
        images = table.column("image").to_pylist()

        for label, img in zip(labels, images, strict=False):
            if label not in wanted_labels:
                continue
            name = wanted_labels[label]
            count = exported.get(name, 0)
            if count >= args.per_person:
                continue

            # image 列是 struct：{bytes: ..., path: ...}
            raw = img.get("bytes") if isinstance(img, dict) else None
            if not raw:
                continue

            person_dir = out_dir / name.replace(" ", "_")
            person_dir.mkdir(parents=True, exist_ok=True)
            (person_dir / f"{count + 1:02d}.jpg").write_bytes(raw)
            exported[name] = count + 1

        if all(exported.get(n, 0) >= args.per_person for n in wanted_labels.values()):
            break

    print(f"\n导出完成，共 {sum(exported.values())} 张，{len(exported)} 位名人：")
    for name, count in sorted(exported.items()):
        print(f"  {name}: {count} 张")
    return 0


if __name__ == "__main__":
    sys.exit(main())
