"""全局配置：路径、阈值、设备选择。

设计原则
--------
1. **模型路径集中管理**：下载脚本只管把文件放进 ``models/``，代码只管找。
2. **阈值不写死**：识别置信度、检测分数、人脸相似度都是「业务判断」，
   放在配置里而不是散落在代码各处 —— 调参时不用翻源码。
3. **设备自动选择**：有 CUDA 就用 CUDA，但 CPU 也能跑（只是慢一点）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# 项目根目录：src/celebrity_recognition/config.py -> 上溯三级
ROOT = Path(__file__).resolve().parents[2]

# 模型与数据目录
MODELS_DIR = Path(os.getenv("CELEB_MODELS_DIR") or (ROOT / "models"))
CLIP_DIR = MODELS_DIR / "clip"
YUNET_PATH = MODELS_DIR / "face_detection_yunet_2023mar.onnx"
SFACE_PATH = MODELS_DIR / "face_recognition_sface_2021dec.onnx"

# 名人候选表与自定义人脸库
# 候选表用**项目内**的 data/candidates.txt（进版本库，开箱即用），
# 不是 models/ 下的 —— models/ 是 gitignore 掉的运行时目录。
CANDIDATES_PATH = Path(
    os.getenv("CELEB_CANDIDATES") or (ROOT / "data" / "candidates.txt")
)
GALLERY_DIR = MODELS_DIR / "gallery"

# 输出目录
OUTPUT_DIR = Path(os.getenv("CELEB_OUTPUT_DIR") or (ROOT / "out"))


@dataclass(frozen=True)
class DetectConfig:
    """人脸检测参数（对应 YuNet 的三个阈值）。"""

    # 置信度阈值：低于此值不认为是人脸
    score_threshold: float = 0.6
    # NMS 阈值：抑制重叠框
    nms_threshold: float = 0.3
    # 输入尺寸（YuNet 内部会按比例缩放）
    input_size: tuple[int, int] = (320, 320)
    # 最多检测多少张脸
    top_k: int = 20


@dataclass(frozen=True)
class RecognizeConfig:
    """识别相关阈值。"""

    # CLIP 归一化相似度阈值：低于此值判为「不认识」
    min_similarity: float = 0.18
    # 返回前 K 个候选
    top_k: int = 5
    # 裁剪人脸时向外扩的比例：脸周围留一点上下文，CLIP 靠上下文也能判断
    crop_padding: float = 0.35
    # 同一人多张脸的合并阈值（SFace 余弦相似度）
    merge_similarity: float = 0.6


@dataclass(frozen=True)
class AppConfig:
    """应用级配置聚合。"""

    detect: DetectConfig = field(default_factory=DetectConfig)
    recognize: RecognizeConfig = field(default_factory=RecognizeConfig)
    models_dir: Path = MODELS_DIR
    clip_dir: Path = CLIP_DIR
    yunet_path: Path = YUNET_PATH
    sface_path: Path = SFACE_PATH
    candidates_path: Path = CANDIDATES_PATH
    gallery_dir: Path = GALLERY_DIR
    output_dir: Path = OUTPUT_DIR

    @property
    def device(self) -> str:
        """默认推理设备。

        **默认用 CPU，不自动切 GPU。**

        原因：本机实测（RTX 5060 / Blackwell sm_120 / torch 2.11.0+cu128）
        在 CLIP 的**文本编码**路径上会抛 ``cudaErrorUnknown`` —— 报错点在
        ``transformers/masking_utils.py`` 的 padding mask 高级索引，
        图像编码正常、文本编码（batch 内长度不等需要 padding）必崩。
        cu128 索引里 torch 最高只到 2.11.0，没有更新的版本可换。

        所以：GPU 是**显式选择**（``--device cuda``），
        且任何 CUDA 错误都会自动退回 CPU（见 ``clip_engine._encode``）。
        CPU 路径已实测可靠：加载 35s、单张 2.2s。

        想用 GPU 且环境没问题，可以设环境变量 ``CELEB_DEVICE=cuda``。
        """
        env = (os.getenv("CELEB_DEVICE") or "").strip().lower()
        if env in ("cuda", "gpu", "cpu"):
            return "cuda" if env != "cpu" else "cpu"
        return "cpu"


def get_config() -> AppConfig:
    """构造默认配置。

    环境变量 ``CELEB_*`` 可覆盖路径，方便把模型放在别处（模型很大，
    放进 git 仓库不合适）。
    """
    return AppConfig()
