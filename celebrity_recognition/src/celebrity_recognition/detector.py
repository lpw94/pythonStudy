"""人脸检测（YuNet，OpenCV DNN）。

为什么选 YuNet
--------------
- OpenCV 5 **自带** ``cv2.FaceDetectorYN``，不需要额外推理框架；
- 模型只有 228KB，CPU 上也够快（几十毫秒一张图）；
- 输出自带 **5 个关键点**（双眼、鼻尖、嘴角），
  这些点对后面的特征提取和画框对齐都很有用。

踩过的坑
--------
``cv2.CascadeClassifier``（Haar）在 **OpenCV 5.0 已被移除**。
所以本项目不用 Haar，改用 DNN 版 YuNet。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from celebrity_recognition.config import DetectConfig


class ModelNotFoundError(RuntimeError):
    """模型文件缺失。"""


@dataclass(frozen=True)
class Face:
    """检测到的一张人脸。

    Attributes:
        x: 左上角 x。
        y: 左上角 y。
        w: 宽。
        h: 高。
        score: 检测置信度（0~1）。
        landmarks: 5 个关键点，形状 (5, 2)，顺序为
            右眼、左眼、鼻尖、右嘴角、左嘴角。
    """

    x: int
    y: int
    w: int
    h: int
    score: float
    landmarks: np.ndarray

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        """返回 (x, y, w, h)。"""
        return (self.x, self.y, self.w, self.h)

    @property
    def center(self) -> tuple[int, int]:
        """人脸中心点。"""
        return (self.x + self.w // 2, self.y + self.h // 2)

    def to_array(self) -> np.ndarray:
        """转成 OpenCV 期望的 1×15 检测结果数组。

        为什么需要这个
        --------------
        ``cv2.FaceRecognizerSF.alignCrop(img, face_box)`` 的第二个参数
        **必须是 numpy 数组**（形状 1×15），不是自定义对象。传 dataclass
        会报::

            (-5:Bad argument) in function 'alignCrop'
            > face_box is not a numpy array, neither a scalar

        15 列的顺序与 YuNet 的输出一致：
        x, y, w, h, 5 个关键点(共 10 个数), score。

        Returns:
            形状 (1, 15) 的 float32 数组。
        """
        return np.asarray(
            [
                self.x,
                self.y,
                self.w,
                self.h,
                *self.landmarks.reshape(-1).tolist(),
                self.score,
            ],
            dtype=np.float32,
        ).reshape(1, 15)


class FaceDetector:
    """YuNet 人脸检测器。

    典型用法::

        detector = FaceDetector(YUNET_PATH)
        faces = detector.detect(image_bgr)
    """

    def __init__(
        self,
        model_path: Path,
        config: DetectConfig | None = None,
    ) -> None:
        """初始化检测器。

        Args:
            model_path: YuNet onnx 模型路径。
            config: 检测参数，None 用默认值。

        Raises:
            ModelNotFoundError: 模型文件不存在。
        """
        if not model_path.exists():
            raise ModelNotFoundError(
                f"找不到人脸检测模型：{model_path}\n"
                f"请先运行 scripts/download_models.py 下载模型。"
            )

        self.config = config or DetectConfig()
        self._detector = cv2.FaceDetectorYN.create(
            str(model_path),
            "",
            self.config.input_size,
            self.config.score_threshold,
            self.config.nms_threshold,
            self.config.top_k,
        )

    def detect(self, image: np.ndarray) -> list[Face]:
        """检测图中的人脸。

        Args:
            image: BGR 彩色图（``cv2.imread`` 的输出）。

        Returns:
            人脸列表，按置信度从高到低排序。
        """
        if image is None or image.size == 0:
            return []

        height, width = image.shape[:2]
        # YuNet 的输入尺寸必须与图片实际尺寸匹配，否则结果全错
        self._detector.setInputSize((width, height))

        _, faces = self._detector.detect(image)
        if faces is None:
            return []

        result: list[Face] = []
        for f in faces:
            # 每行 15 个数：x, y, w, h, 5 个关键点(10), score
            x, y, w, h = (int(v) for v in f[:4])
            landmarks = np.asarray(f[4:14], dtype=np.float32).reshape(5, 2)
            score = float(f[14])
            result.append(Face(x, y, w, h, score, landmarks))

        result.sort(key=lambda f: f.score, reverse=True)
        return result


def crop_face(
    image: np.ndarray,
    face: Face,
    padding: float = 0.35,
) -> np.ndarray:
    """按人脸框裁剪图像，并向外留白。

    为什么留白
    ----------
    CLIP 是**整图**模型，不是人脸专用模型。裁得太紧只剩五官，
    会丢掉发型、脸型、年龄、妆造这些同样有判别力的信息；
    裁得太松又会引入背景干扰。留 30%~40% 是经验值。

    Args:
        image: BGR 彩色图。
        face: 人脸框。
        padding: 向外扩展的比例（相对人脸尺寸）。

    Returns:
        裁剪出的 BGR 图像；框超出图片时自动贴边裁剪。
    """
    height, width = image.shape[:2]
    pad_x = int(face.w * padding)
    pad_y = int(face.h * padding)

    x1 = max(0, face.x - pad_x)
    y1 = max(0, face.y - pad_y)
    x2 = min(width, face.x + face.w + pad_x)
    y2 = min(height, face.y + face.h + pad_y)

    return image[y1:y2, x1:x2].copy()
