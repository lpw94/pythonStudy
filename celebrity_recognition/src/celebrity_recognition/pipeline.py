"""识别流程编排：检测 → 裁剪 → 识别 → 合并 → 输出。

流程设计
--------
::

    图片
      ↓  YuNet 检测
    N 张人脸
      ↓  裁剪（带留白）
    N 张人脸图
      ↓  CLIP 零样本  →  Top-K 候选
      ↓  SFace 特征库 →  精确匹配（若建了库）
    每张脸一条结论
      ↓  SFace 特征聚类，合并同一个人
    最终结果

为什么要「合并同一个人」
------------------------
一张合影里同一个人可能出现多次。逐个报一遍会得到
「流、两岸、三郎」这种荒谬输出 —— 因为 CLIP 每次给的名字可能略有差异。
用 SFace 特征做聚类（同一人合并，取最高置信度的那次），
输出才符合人的直觉。

置信度决策顺序
--------------
人脸库结果**优先于** CLIP 结果：库是拿真实参考图比出来的，
比「看起来像」可靠得多。但库相似度不过阈值时，回落到 CLIP。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from celebrity_recognition.candidates import Candidate, load_candidates
from celebrity_recognition.clip_engine import ClipEngine, Match
from celebrity_recognition.config import AppConfig, get_config
from celebrity_recognition.detector import Face, FaceDetector, crop_face
from celebrity_recognition.gallery import (
    FaceRecognizer,
    GalleryIndex,
    GalleryMatch,
    build_gallery,
)
from celebrity_recognition.render import LabelInfo, render

# 来源标识
SOURCE_GALLERY = "gallery"  # 人脸特征库命中
SOURCE_CLIP = "clip"  # CLIP 零样本
SOURCE_UNKNOWN = "unknown"  # 都不够确信


@dataclass
class FaceResult:
    """单张人脸的识别结论。

    Attributes:
        face: 人脸框。
        matches: CLIP 的 Top-K 候选。
        gallery_match: 人脸库匹配结果（未建库时为 None）。
        name: 最终认定的名字。
        confidence: 最终置信度（0~1）。
        source: 结论来源。
        merged_from: 被合并到本条的其他脸框数量。
    """

    face: Face
    matches: list[Match]
    gallery_match: GalleryMatch | None
    name: str
    confidence: float
    source: str
    merged_from: int = 0

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        """人脸框 (x, y, w, h)。"""
        return self.face.bbox

    def to_dict(self) -> dict[str, Any]:
        """转成可 JSON 序列化的字典。"""
        return {
            "bbox": list(self.bbox),
            "detection_score": round(self.face.score, 4),
            "name": self.name,
            "confidence": round(self.confidence, 4),
            "source": self.source,
            "merged_from": self.merged_from,
            "top_matches": [
                {"name": m.display, "similarity": round(m.similarity, 4)}
                for m in self.matches
            ],
            "gallery_match": (
                {
                    "name": self.gallery_match.name,
                    "similarity": round(self.gallery_match.similarity, 4),
                }
                if self.gallery_match
                else None
            ),
        }


@dataclass
class RecognitionResult:
    """整张图的识别结果。

    Attributes:
        results: 每张人脸的结论（**同一人已合并**）。
        detected_count: 原始检测到的人脸数（合并前）。
        image_width: 原图宽。
        image_height: 原图高。
        engine_info: 引擎信息。
    """

    results: list[FaceResult] = field(default_factory=list)
    detected_count: int = 0
    image_width: int = 0
    image_height: int = 0
    engine_info: dict[str, Any] = field(default_factory=dict)

    @property
    def face_count(self) -> int:
        """不同的人的数量（合并同一人之后）。"""
        return len(self.results)

    @property
    def identified(self) -> list[FaceResult]:
        """成功认出的（有人名的）人脸。"""
        return [r for r in self.results if r.source != SOURCE_UNKNOWN]

    def to_dict(self) -> dict[str, Any]:
        """转成可 JSON 序列化的字典。"""
        return {
            "image": {"width": self.image_width, "height": self.image_height},
            "detected_count": self.detected_count,
            "person_count": self.face_count,
            "engine": self.engine_info,
            "faces": [r.to_dict() for r in self.results],
        }


def imread_unicode(path: Path | str) -> np.ndarray | None:
    """读取图片，兼容中文路径。

    为什么不用 ``cv2.imread``
    ----------------------
    ``cv2.imread`` 内部用 C 的 ``fopen`` 打开文件，**在 Windows 上无法处理
    非 ASCII 路径** —— 传中文路径会静默返回 ``None``，没有任何报错。
    这是个非常容易踩的坑：代码看着完全正常，结果就是读不出图。

    解法是 ``np.fromfile`` 读字节 + ``cv2.imdecode`` 解码，绕开文件系统编码。

    Args:
        path: 图片路径。

    Returns:
        BGR 图像；读取失败返回 None。
    """
    path = Path(path)
    if not path.exists():
        return None
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
    except OSError:
        return None
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


class Recognizer:
    """名人识别器：把上面所有部件串起来。

    典型用法::

        rec = Recognizer()
        result = rec.recognize("photo.jpg")
    """

    def __init__(
        self,
        config: AppConfig | None = None,
        device: str | None = None,
        use_gallery: bool = True,
    ) -> None:
        """初始化。

        Args:
            config: 应用配置。
            device: 推理设备，None 表示自动选择。
            use_gallery: 是否启用人脸特征库。
        """
        self.config = config or get_config()
        self.device = device or self.config.device

        self.detector = FaceDetector(self.config.yunet_path, self.config.detect)
        self.clip = ClipEngine(self.config.clip_dir, device=self.device)

        self.candidates: list[Candidate] = load_candidates(
            builtin=True, extra_path=self.config.candidates_path
        )

        # 人脸库（可选）
        self.gallery: GalleryIndex | None = None
        self._recognizer: FaceRecognizer | None = None
        if use_gallery and self.config.gallery_dir.exists():
            self._recognizer = FaceRecognizer(self.config.sface_path)
            self.gallery = build_gallery(
                self.config.gallery_dir, self.detector, self._recognizer
            )
            if len(self.gallery) == 0:
                self.gallery = None

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------
    def _features(self, image: np.ndarray, faces: list[Face]) -> list[np.ndarray]:
        """提取所有脸的 SFace 特征（用于合并同一人）。

        Args:
            image: BGR 图。
            faces: 人脸列表。

        Returns:
            与 faces 等长的特征列表；某张脸失败时用零向量占位。
        """
        if self._recognizer is None:
            return [np.zeros(128, dtype=np.float32) for _ in faces]
        feats: list[np.ndarray] = []
        for face in faces:
            try:
                feats.append(self._recognizer.feature(image, face))
            except cv2.error:
                feats.append(np.zeros(128, dtype=np.float32))
        return feats

    def _merge_same_person(
        self,
        results: list[FaceResult],
        features: list[np.ndarray],
    ) -> list[FaceResult]:
        """合并同一个人（合影里同一人只报一次）。

        Args:
            results: 每张脸的结果。
            features: 对应的 SFace 特征。

        Returns:
            合并后的结果列表，按置信度降序。
        """
        if len(results) <= 1 or self._recognizer is None:
            return results

        threshold = self.config.recognize.merge_similarity
        groups: list[list[int]] = []

        for i in range(len(results)):
            placed = False
            for group in groups:
                rep = group[0]
                sim = float(np.dot(features[i], features[rep]))
                if sim >= threshold:
                    group.append(i)
                    placed = True
                    break
            if not placed:
                groups.append([i])

        merged: list[FaceResult] = []
        for group in groups:
            # 组内取置信度最高的那条作为代表
            best = max(group, key=lambda i: results[i].confidence)
            item = results[best]
            item.merged_from = len(group) - 1
            merged.append(item)

        merged.sort(key=lambda r: r.confidence, reverse=True)
        return merged

    def _decide(
        self,
        matches: list[Match],
        gallery_match: GalleryMatch | None,
    ) -> tuple[str, float, str]:
        """决定最终结论。

        Args:
            matches: CLIP 候选。
            gallery_match: 人脸库匹配。

        Returns:
            (名字, 置信度, 来源)。
        """
        rec = self.config.recognize

        # 人脸库优先：拿参考图比出来的结果比「看起来像」可靠
        if gallery_match and gallery_match.similarity >= 0.5:
            return (
                self._display_name(gallery_match.name),
                gallery_match.similarity,
                SOURCE_GALLERY,
            )

        if matches and matches[0].similarity >= rec.min_similarity:
            return matches[0].display, matches[0].similarity, SOURCE_CLIP

        return "未识别", 0.0, SOURCE_UNKNOWN

    def _display_name(self, english_name: str) -> str:
        """把人脸库里的英文名转成统一的展示格式。

        两个引擎的输出必须长得一样，否则同一次识别里会出现
        「Tom Cruise」和「汤姆·克鲁斯（Tom Cruise）」混排。
        这里用候选表把英文名换成「中文名（英文名）」。

        Args:
            english_name: 人脸库里的名字。

        Returns:
            展示名；候选表里找不到时原样返回。
        """
        target = english_name.strip().lower()
        for cand in self.candidates:
            if cand.en.strip().lower() == target:
                return cand.display
        return english_name

    # ------------------------------------------------------------------
    # 对外接口
    # ------------------------------------------------------------------
    def recognize(
        self,
        image_path: Path | str,
        top_k: int | None = None,
    ) -> tuple[RecognitionResult, np.ndarray]:
        """识别一张图片里的名人。

        Args:
            image_path: 图片路径（支持中文）。
            top_k: 返回的候选数量，None 用配置值。

        Returns:
            (识别结果, 原始 BGR 图)。图片读不出来时结果为空。

        Raises:
            FileNotFoundError: 图片不存在。
        """
        top_k = top_k or self.config.recognize.top_k
        image = imread_unicode(image_path)
        if image is None:
            raise FileNotFoundError(f"无法读取图片：{image_path}")

        height, width = image.shape[:2]
        faces = self.detector.detect(image)

        result = RecognitionResult(
            image_width=width,
            image_height=height,
            engine_info={
                # 用 clip.device 而不是 self.device —— 显存不足时引擎会退回 CPU，
                # 报出来的必须是**实际用的**设备
                "device": self.clip.device,
                "candidates": len(self.candidates),
                "fallback": self.clip.fallback_reason,
            },
        )

        if not faces:
            return result, image

        crops = [crop_face(image, f, self.config.recognize.crop_padding) for f in faces]
        all_matches = self.clip.classify(crops, self.candidates, top_k=top_k)
        features = self._features(image, faces)

        face_results: list[FaceResult] = []
        for face, matches, feat in zip(faces, all_matches, features, strict=False):
            gmatch: GalleryMatch | None = None
            if self.gallery is not None and np.any(feat):
                gmatch = self.gallery.match(feat)

            name, confidence, source = self._decide(matches, gmatch)
            face_results.append(
                FaceResult(
                    face=face,
                    matches=matches,
                    gallery_match=gmatch,
                    name=name,
                    confidence=confidence,
                    source=source,
                )
            )

        result.results = self._merge_same_person(face_results, features)
        result.detected_count = len(faces)
        return result, image

    def render_result(
        self,
        result: RecognitionResult,
        image: np.ndarray,
        output_path: Path | None = None,
    ) -> np.ndarray:
        """把结果画到图上。

        Args:
            result: 识别结果。
            image: 原始 BGR 图。
            output_path: 输出路径；None 则不写文件。

        Returns:
            绘制后的 BGR 图。
        """
        boxes = [r.bbox for r in result.results]
        labels = [
            LabelInfo(
                title=r.name,
                subtitle=f"{r.confidence:.0%}" if r.source != SOURCE_UNKNOWN else "",
                color=(
                    (60, 190, 60)
                    if r.source == SOURCE_GALLERY
                    else (70, 160, 240)
                    if r.source == SOURCE_CLIP
                    else (150, 150, 150)
                ),
            )
            for r in result.results
        ]
        return render(image, boxes, labels, output_path=output_path)


def format_report(result: RecognitionResult) -> str:
    """把识别结果格式化成人类可读的文本。

    Args:
        result: 识别结果。

    Returns:
        多行文本报告。
    """
    lines: list[str] = []
    if result.detected_count != result.face_count:
        # 合影里同一个人出现多次时会合并，合并前后的数字不一样，
        # 只报一个数会让人以为漏检了
        lines.append(
            f"图片 {result.image_width}×{result.image_height}，"
            f"检测到 {result.detected_count} 张人脸，"
            f"合并同一个人后是 {result.face_count} 个人"
            f"（{result.face_count - len(result.identified)} 人未识别）"
        )
    else:
        lines.append(
            f"图片 {result.image_width}×{result.image_height}，"
            f"检测到 {result.face_count} 张人脸"
            f"（{result.face_count - len(result.identified)} 张未识别）"
        )

    if not result.results:
        lines.append("→ 没有检测到人脸。可以尝试更清晰、人物更明显的图片。")
        return "\n".join(lines)

    for i, r in enumerate(result.results, 1):
        source_label = {
            SOURCE_GALLERY: "人脸库",
            SOURCE_CLIP: "CLIP",
            SOURCE_UNKNOWN: "未识别",
        }.get(r.source, r.source)

        merged = f"，合并了 {r.merged_from} 张同脸" if r.merged_from else ""
        lines.append("")
        lines.append(
            f"[{i}] {r.name}  置信度 {r.confidence:.1%}"
            f"  （来源：{source_label}{merged}）"
        )
        lines.append(
            f"    位置：x={r.bbox[0]} y={r.bbox[1]}"
            f" w={r.bbox[2]} h={r.bbox[3]}"
        )

        if r.matches:
            alts = "、".join(
                f"{m.display} {m.similarity:.0%}" for m in r.matches[:3]
            )
            lines.append(f"    其它候选：{alts}")

        if r.gallery_match and r.source != SOURCE_GALLERY:
            lines.append(
                f"    人脸库最接近：{r.gallery_match.name} "
                f"{r.gallery_match.similarity:.1%}（低于阈值，不采信）"
            )

    return "\n".join(lines)
