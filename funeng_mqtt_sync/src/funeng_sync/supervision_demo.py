"""supervision 最小练手：OpenCV 轮廓检测 -> supervision 画框 -> 存盘。

为什么不用 YOLO：YOLO 需要 torch（几百 MB），对练手太重。supervision 的核心价值
是「统一检测输出 + 一套可视化 API」，与具体检测模型无关——所以这里用 OpenCV 的
findContours 做一个轻量「检测器」找图中较大连通区域，把框交给 supervision 的
BoxAnnotator 画出来，证明它「模型无关」。

注意：opencv 5.0 已移除传统 Haar 级联（CascadeClassifier / haarcascades 数据），
故改用轮廓检测，对任意图片都能跑出真实框。

依赖：opencv（.py312 已随 ddddocr 装好）+ supervision（需 pip install supervision）

运行（用 3.12 环境，从任意目录跑都行）：
    PY=../.py312/python.exe      # 项目根的 embeddable 3.12

    $PY -m funeng_sync.supervision_demo img/1.jpeg   # 指定图片
    $PY -m funeng_sync.supervision_demo 1.jpeg        # 只在 img/ 里找同名
    $PY -m funeng_sync.supervision_demo# 自动取 img/ 第一张

路径解析规则见 resolve_img_path()：先按原样解析，找不到就回退到本项目 img/
目录下同名文件，所以「从哪个目录启动」不影响结果。
支持 jpg / jpeg / png / bmp / webp。
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import supervision as sv

ROOT = Path(__file__).resolve().parents[2]
IMG_DIR = ROOT / "img"
OUT_DIR = ROOT / "out"

# 支持的图片后缀（小写）。默认扫描 img/ 时用这个集合，
# 避免只认 .jpg 而漏掉 .jpeg / .png
IMG_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def detect_regions(
    image: np.ndarray, max_boxes: int = 10, min_area_ratio: float = 0.01
):
    """用 OpenCV 轮廓检测模拟一个真实检测器：找图中较大的连通区域。

    返回 (x, y, w, h) 列表。真实项目里把这段换成 YOLO / Haar / 任何模型即可，
    下游 supervision 的可视化代码完全不用改。
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # 二值化：验证码多为白底黑字，反相让文字成前景；OTSU 自动取阈值
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h, w = image.shape[:2]
    min_area = h * w * min_area_ratio
    boxes = []
    for cnt in contours:
        x, y, bw, bh = cv2.boundingRect(cnt)
        if bw * bh >= min_area:
            boxes.append((x, y, bw, bh))
    # 按面积从大到小，取前 max_boxes，避免细碎轮廓刷屏
    boxes.sort(key=lambda b: b[2] * b[3], reverse=True)
    return boxes[:max_boxes]


def to_detections(boxes) -> sv.Detections:
    """把 (x, y, w, h) 转成 supervision 要求的 xyxy 格式。"""
    if len(boxes) == 0:
        return sv.Detections.empty()
    xyxy = [[x, y, x + w, y + h] for (x, y, w, h) in boxes]
    return sv.Detections(xyxy=np.array(xyxy, dtype=np.float32))


def annotate_and_save(
    image: np.ndarray, detections: sv.Detections, out_path: Path
) -> Path:
    """用 supervision 的 BoxAnnotator 画框 + LabelAnnotator 加标签，保存到 out/。"""
    box_annotator = sv.BoxAnnotator(color_lookup=sv.ColorLookup.INDEX)
    label_annotator = sv.LabelAnnotator(color_lookup=sv.ColorLookup.INDEX)
    labels = [f"region {i}" for i in range(len(detections))]
    annotated = box_annotator.annotate(scene=image.copy(), detections=detections)
    annotated = label_annotator.annotate(
        scene=annotated, detections=detections, labels=labels
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), annotated)
    return out_path


def demo_with_sample_boxes(image: np.ndarray, out_path: Path) -> Path:
    """降级：没检测到人脸时画几个示例框，证明 annotator 本身工作正常。"""
    h, w = image.shape[:2]
    xyxy = np.array(
        [
            [int(w * 0.1), int(h * 0.1), int(w * 0.4), int(h * 0.4)],
            [int(w * 0.5), int(h * 0.5), int(w * 0.9), int(h * 0.9)],
        ],
        dtype=np.float32,
    )
    detections = sv.Detections(xyxy=xyxy)
    box_annotator = sv.BoxAnnotator(color_lookup=sv.ColorLookup.INDEX)
    label_annotator = sv.LabelAnnotator(color_lookup=sv.ColorLookup.INDEX)
    annotated = box_annotator.annotate(scene=image.copy(), detections=detections)
    annotated = label_annotator.annotate(
        scene=annotated, detections=detections, labels=["sample A", "sample B"]
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), annotated)
    return out_path


def _all_imgs() -> list[Path]:
    """列出 img/ 下所有图片（多后缀，按文件名排序，结果稳定）。"""
    return sorted(
        (
            p
            for p in IMG_DIR.iterdir()
            if p.is_file() and p.suffix.lower() in IMG_SUFFIXES
        ),
        key=lambda p: p.name,
    )


def resolve_img_path(arg: str | None) -> Path | None:
    """把命令行参数解析成真实图片路径。

    解析顺序（关键：不依赖当前工作目录，从哪个目录跑都能用）：
    1. 参数本身（支持 .\\img\\1.jpeg / D:\\xx\\1.jpeg 这类带目录写法）；
    2. 回退到项目 img/ 目录下同名文件（所以 `img/1.jpeg` 和 `1.jpeg` 都行）；
    3. 什么都不传时，自动取 img/ 里按名字排序的第一张。
    """
    if not arg:
        imgs = _all_imgs()
        return imgs[0] if imgs else None

    # 1) 原样解析（用户可能传了绝对路径或带正确相对目录）
    p = Path(arg).expanduser()
    if p.is_file():
        return p

    # 2) 回退：只取文件名，去 img/ 里找
    #    这样即使从别的目录跑、或路径分隔符写成 / 或 \，都能命中
    candidate = IMG_DIR / p.name
    if candidate.is_file():
        return candidate

    return None


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    img_path = resolve_img_path(arg)

    if img_path is None:
        search = IMG_DIR if arg is None else (IMG_DIR / Path(arg).name)
        print(f"未找到图片：{arg if arg else search}")
        print(f"已尝试：{Path(arg).resolve() if arg else '(未传参数)'}")
        print(f"           ->  {search.resolve()}")
        avail = _all_imgs()
        if avail:
            print(f"img/ 目录现有图片（{len(avail)} 张）：")
            for p in avail[:10]:
                print(f"  - {p.name}")
        else:
            print(f"img/ 目录为空：{IMG_DIR}")
        sys.exit(1)

    image = cv2.imread(str(img_path))
    if image is None:
        print(f"读取图片失败：{img_path}")
        sys.exit(1)

    boxes = detect_regions(image)
    out_path = OUT_DIR / f"sup_{img_path.stem}.jpg"

    if len(boxes) > 0:
        detections = to_detections(boxes)
        saved = annotate_and_save(image, detections, out_path)
        print(f"OpenCV 找到 {len(boxes)} 个区域，已用 supervision 画框保存：{saved}")
    else:
        saved = demo_with_sample_boxes(image, out_path)
        print(f"未找到足够大的区域，降级画示例框演示 annotator：{saved}")


if __name__ == "__main__":
    main()
