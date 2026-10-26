"""生成一张多人合影，用于验证多脸检测与「同一人合并」逻辑。

为什么要专门造这张图
--------------------
单张人脸照测不出两件事：

1. **多脸检测** —— 一张图里能不能同时框出好几个人；
2. **同一人合并** —— 合影里同一个人出现两次时，会不会报成两个人。

做法：把同一个人的两张参考图拼在一起（模拟合影），
再加两个不同的人，凑成一张 4 脸图。
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "img/celebrity_samples"
OUT = ROOT / "img/celebrity_samples/合成的合影.jpg"

# (人物目录, 要用第几张)
LAYOUT = [
    ("Tom_Cruise", "05.jpg"),
    ("Tom_Cruise", "06.jpg"),  # 同一个人，故意重复
    ("Emma_Watson", "05.jpg"),
    ("Lionel_Messi", "05.jpg"),
]


def read(folder: str, name: str) -> np.ndarray | None:
    """读一张样本图。

    Args:
        folder: 人物目录名。
        name: 文件名。

    Returns:
        BGR 图；读不到返回 None。
    """
    path = SAMPLES / folder / name
    if not path.exists():
        return None
    data = np.fromfile(str(path), dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def main() -> int:
    """拼图并保存。

    Returns:
        退出码。
    """
    tiles = []
    for folder, name in LAYOUT:
        img = read(folder, name)
        if img is None:
            print(f"  跳过 {folder}/{name}（不存在）")
            continue
        tiles.append(img)

    if len(tiles) < 2:
        print("素材不足，无法生成合影")
        return 1

    size = 256
    tiles = [cv2.resize(t, (size, size)) for t in tiles]
    cols = 2
    rows = (len(tiles) + cols - 1) // cols

    canvas = np.full((rows * size, cols * size, 3), 40, dtype=np.uint8)
    for i, tile in enumerate(tiles):
        r, c = divmod(i, cols)
        canvas[r * size : (r + 1) * size, c * size : (c + 1) * size] = tile

    OUT.parent.mkdir(parents=True, exist_ok=True)
    # 用 imencode + tofile，避免中文路径在 cv2.imwrite 上出问题
    ok, buf = cv2.imencode(".jpg", canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    if not ok:
        print("编码失败")
        return 1
    buf.tofile(str(OUT))

    print(f"已生成 {OUT}")
    print(f"包含 {len(tiles)} 张脸（其中 2 张是同一个人：Tom Cruise）")
    print(f"尺寸：{canvas.shape[1]}×{canvas.shape[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
