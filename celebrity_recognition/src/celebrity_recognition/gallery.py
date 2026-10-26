"""人脸特征库（SFace）——「精确匹配」引擎。

为什么还需要它
--------------
CLIP 是**语义**匹配：它回答「这张脸看起来最像哪个名人」。
它并不知道「这就是本人」，只是分类。

人脸特征库是**身份**匹配：把人脸编码成一个 128 维特征向量，
和库里每位名人的参考图特征做余弦比对，相似度超过阈值就是同一个人。

两者互补
--------
| 引擎 | 问的问题 | 优点 | 局限 |
|------|---------|------|------|
| CLIP 零样本 | 像不像某个名人 | 免建库，覆盖广 | 不是身份认定 |
| SFace 特征库 | 是不是这个人 | 准确，可用于「是不是同一人」 | 需要参考图 |

用法::

    gallery/
      成龙/  01.jpg  02.jpg
      迪丽热巴/ 01.jpg

建库后，人脸库的结果会**覆盖** CLIP 的结果（因为它更确定）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from celebrity_recognition.detector import Face, FaceDetector, crop_face

# 支持的图片后缀
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


class GalleryError(RuntimeError):
    """人脸库相关错误。"""


@dataclass(frozen=True)
class GalleryMatch:
    """人脸库匹配结果。

    Attributes:
        name: 名人名字（目录名）。
        similarity: 余弦相似度。
    """

    name: str
    similarity: float


@dataclass
class GalleryEntry:
    """库中的一条记录。

    Attributes:
        name: 名人名字。
        feature: 归一化后的特征向量。
    """

    name: str
    feature: np.ndarray


class FaceRecognizer:
    """SFace 人脸特征提取器。

    典型用法::

        rec = FaceRecognizer(SFACE_PATH)
        feat = rec.feature(image_bgr, face)
    """

    def __init__(self, model_path: Path) -> None:
        """初始化。

        Args:
            model_path: SFace onnx 模型路径。

        Raises:
            GalleryError: 模型缺失或 OpenCV 不支持 FaceRecognizerSF。
        """
        if not model_path.exists():
            raise GalleryError(
                f"找不到人脸识别模型：{model_path}\n"
                f"请先运行 scripts/download_models.py 下载模型。"
            )
        if not hasattr(cv2, "FaceRecognizerSF"):
            raise GalleryError(
                "当前 OpenCV 版本不支持 FaceRecognizerSF（需要 OpenCV 4.5.4+）。"
            )

        self._recognizer = cv2.FaceRecognizerSF.create(str(model_path), "")

    def feature(self, image: np.ndarray, face: Face) -> np.ndarray:
        """提取人脸特征向量。

        Args:
            image: BGR 彩色图。
            face: 人脸框（含 5 个关键点，SFace 的对齐依赖它们）。

        Returns:
            128 维 float32 向量，已 L2 归一化。
        """
        # alignCrop 会按关键点把人脸摆正 —— 不对齐的话，
        # 同一张脸稍微歪一点，特征就会明显偏移。
        # ⚠️ 第二个参数必须是 numpy 数组（1×15），传 dataclass 会报
        #    "face_box is not a numpy array, neither a scalar"。
        aligned = self._recognizer.alignCrop(image, face.to_array())
        feat = self._recognizer.feature(aligned)
        vec = np.asarray(feat, dtype=np.float32).ravel()
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec = vec / norm
        return vec


class GalleryIndex:
    """人脸特征库索引。

    库的组织方式是「一个名人一个目录，目录里放参考图」::

        gallery/成龙/01.jpg

    目录名就是人名 —— 这样维护成本最低，用户不需要理解任何格式。
    """

    def __init__(self, entries: list[GalleryEntry] | None = None) -> None:
        """初始化索引。

        Args:
            entries: 初始条目。
        """
        self.entries: list[GalleryEntry] = entries or []

    def __len__(self) -> int:
        return len(self.entries)

    @property
    def names(self) -> list[str]:
        """库中所有的人名（去重）。"""
        seen: list[str] = []
        for e in self.entries:
            if e.name not in seen:
                seen.append(e.name)
        return seen

    def add(self, name: str, feature: np.ndarray) -> None:
        """加入一条记录。

        Args:
            name: 人名。
            feature: 特征向量。
        """
        self.entries.append(GalleryEntry(name=name, feature=feature))

    def match(self, feature: np.ndarray) -> GalleryMatch | None:
        """在库中查找最相似的人。

        Args:
            feature: 待查询的特征向量。

        Returns:
            最佳匹配；库为空时返回 None。
        """
        if not self.entries:
            return None

        query = np.asarray(feature, dtype=np.float32).ravel()
        qnorm = float(np.linalg.norm(query))
        if qnorm == 0:
            return None
        query = query / qnorm

        best_name = ""
        best_sim = -1.0
        for entry in self.entries:
            sim = float(np.dot(query, entry.feature))
            if sim > best_sim:
                best_sim = sim
                best_name = entry.name

        return GalleryMatch(name=best_name, similarity=best_sim)


def build_gallery(
    gallery_dir: Path,
    detector: FaceDetector,
    recognizer: FaceRecognizer,
    verbose: bool = False,
) -> GalleryIndex:
    """扫描人脸库目录并建立索引。

    对每张参考图：**先检测人脸再取最大的一张**。
    参考图常常是合影或带背景的海报，直接对整图取特征会拿到垃圾。

    Args:
        gallery_dir: 人脸库根目录。
        detector: 人脸检测器。
        recognizer: 特征提取器。
        verbose: 是否打印进度。

    Returns:
        建好的索引。

    Raises:
        GalleryError: 人脸库目录不存在。
    """
    if not gallery_dir.exists():
        raise GalleryError(f"人脸库目录不存在：{gallery_dir}")

    index = GalleryIndex()
    image_count = 0

    for person_dir in sorted(p for p in gallery_dir.iterdir() if p.is_dir()):
        # 目录名用下划线（"Tom_Cruise"），显示时还原成空格（"Tom Cruise"）。
        # 目录名直接当人名会出现在最终输出里，带下划线很难看。
        name = person_dir.name.replace("_", " ")
        for img_path in sorted(person_dir.iterdir()):
            if img_path.suffix.lower() not in IMAGE_SUFFIXES:
                continue

            image = cv2.imread(str(img_path))
            if image is None:
                if verbose:
                    print(f"  跳过无法读取的图片：{img_path.name}")
                continue

            faces = detector.detect(image)
            if not faces:
                if verbose:
                    print(f"  {name}/{img_path.name}：未检测到人脸，跳过")
                continue

            # 取置信度最高（面积通常也最大）的那张脸
            face = max(faces, key=lambda f: f.score)
            try:
                feat = recognizer.feature(image, face)
            except cv2.error as e:
                if verbose:
                    print(f"  {name}/{img_path.name}：特征提取失败（{e}）")
                continue

            index.add(name, feat)
            image_count += 1
            if verbose:
                print(f"  ✓ {name}/{img_path.name}（检测分 {face.score:.2f}）")

    if verbose:
        print(f"人脸库建立完成：{image_count} 张参考图，{len(index.names)} 位名人")
    return index


def gallery_from_crops(
    gallery_dir: Path,
    detector: FaceDetector,
    recognizer: FaceRecognizer,
) -> GalleryIndex:
    """便捷入口：直接建库。

    Args:
        gallery_dir: 人脸库目录。
        detector: 检测器。
        recognizer: 特征提取器。

    Returns:
        索引。
    """
    return build_gallery(gallery_dir, detector, recognizer)


__all__ = [
    "FaceRecognizer",
    "GalleryEntry",
    "GalleryError",
    "GalleryIndex",
    "GalleryMatch",
    "build_gallery",
    "crop_face",
    "gallery_from_crops",
]
