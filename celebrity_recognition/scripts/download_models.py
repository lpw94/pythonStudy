"""模型下载脚本。

为什么要有这个脚本
------------------
模型文件总共约 600MB，**不能进 git 仓库**。所以把「从哪下、怎么下」
固化成脚本，而不是写在文档里让人自己找。

网络前提（本机实测）
--------------------
- ``pypi.org`` 直连可用
- ``huggingface.co`` **不通** → 用镜像 ``hf-mirror.com``
- ``raw.githubusercontent.com`` **不通** → opencv_zoo 的 LFS 文件走
  ``media.githubusercontent.com/media/...``（这是 LFS 的真实内容域名）

运行::

    E:/workBuddy/pythonStudy/.py312/python.exe scripts/download_models.py
"""

from __future__ import annotations

import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ROOT / "models"

# opencv_zoo 的模型走 LFS 域名，raw.githubusercontent.com 在本机不通
YUNET_URL = (
    "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/"
    "models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
)
SFACE_URL = (
    "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/"
    "models/face_recognition_sface/face_recognition_sface_2021dec.onnx"
)

CLIP_BASE = "https://hf-mirror.com/openai/clip-vit-base-patch32/resolve/main"
CLIP_FILES = (
    "config.json",
    "preprocessor_config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.json",
    "merges.txt",
    "special_tokens_map.json",
    "pytorch_model.bin",
)

# 期望大小，用于识别「下载到的是错误页面而不是文件」
EXPECTED_MIN_SIZE = {
    "pytorch_model.bin": 500 * 1024 * 1024,
    "face_recognition_sface_2021dec.onnx": 30 * 1024 * 1024,
    "face_detection_yunet_2023mar.onnx": 100 * 1024,
    "tokenizer.json": 1 * 1024 * 1024,
}


def download(url: str, dest: Path, min_size: int = 0) -> bool:
    """下载单个文件。

    Args:
        url: 下载地址。
        dest: 目标路径。
        min_size: 期望的最小字节数；小于它说明下到的不是真文件。

    Returns:
        是否成功。
    """
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists() and dest.stat().st_size >= min_size > 0:
        size_mb = dest.stat().st_size / 1024 / 1024
        print(f"  ✓ 已存在 {dest.name}（{size_mb:.1f} MB），跳过")
        return True

    print(f"  ↓ 下载 {dest.name} …")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as resp, dest.open("wb") as fh:
            while True:
                chunk = resp.read(1024 * 256)
                if not chunk:
                    break
                fh.write(chunk)
    except Exception as e:
        print(f"  ✗ 失败：{e}")
        return False

    size = dest.stat().st_size
    if min_size and size < min_size:
        print(f"  ✗ 文件过小（{size} 字节），可能下到了错误页面")
        return False

    print(f"  ✓ {dest.name}（{size / 1024 / 1024:.1f} MB）")
    return True


def main() -> int:
    """下载全部模型。

    Returns:
        退出码：0 全部成功，1 有失败。
    """
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    print("下载人脸检测模型（YuNet）")
    ok = download(
        YUNET_URL, MODELS_DIR / "face_detection_yunet_2023mar.onnx",
        EXPECTED_MIN_SIZE["face_detection_yunet_2023mar.onnx"],
    )

    print("下载人脸识别模型（SFace）")
    ok &= download(
        SFACE_URL, MODELS_DIR / "face_recognition_sface_2021dec.onnx",
        EXPECTED_MIN_SIZE["face_recognition_sface_2021dec.onnx"],
    )

    print("下载 CLIP 模型")
    for name in CLIP_FILES:
        ok &= download(
            f"{CLIP_BASE}/{name}",
            MODELS_DIR / "clip" / name,
            EXPECTED_MIN_SIZE.get(name, 0),
        )

    print()
    if ok:
        print("全部模型就绪。")
        return 0
    print("部分模型下载失败，请检查网络后重试。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
