"""名人明星识别：给一张图，认出里面的人。

模块划分
--------
- config:      路径、阈值、设备选择
- candidates:  候选名人表（中英对照）
- detector:    YuNet 人脸检测
- clip_engine: CLIP 零样本分类
- gallery:     SFace 人脸特征库（精确匹配）
- pipeline:    流程编排（检测 → 识别 → 合并）
- render:      标注图渲染（OpenCV 画框 + PIL 画中文）
- cli:         命令行入口
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = [
    "candidates",
    "clip_engine",
    "config",
    "detector",
    "gallery",
    "pipeline",
    "render",
]
