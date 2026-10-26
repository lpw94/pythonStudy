"""人脸特征库（SFace）的 leave-one-out 评估。

为什么必须是 leave-one-out
--------------------------
如果用同一张图既建库又测试，准确率会接近 100% —— 那只是**记住了这张图**，
不是认出了这个人。诚实的做法是：用这个人的**其它**图建库，
用没见过的图去测。

数据划分
--------
``img/celebrity_samples/<名字>/01..10.jpg``：

- 01~04：建库参考图
- 05~10：测试图（模型从没见过）

跑法::

    E:/workBuddy/pythonStudy/.py312/python.exe scripts/evaluate_gallery.py \
        --samples img/celebrity_samples
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from celebrity_recognition.config import get_config
from celebrity_recognition.detector import FaceDetector
from celebrity_recognition.gallery import FaceRecognizer, GalleryIndex
from celebrity_recognition.pipeline import imread_unicode

GALLERY_COUNT = 4  # 前 4 张用于建库


def main() -> int:
    """跑 leave-one-out 评估。

    Returns:
        退出码。
    """
    parser = argparse.ArgumentParser(description="评估人脸特征库识别准确率")
    parser.add_argument("--samples", required=True, help="样本目录")
    parser.add_argument("--threshold", type=float, default=0.5, help="匹配阈值")
    args = parser.parse_args()

    config = get_config()
    detector = FaceDetector(config.yunet_path, config.detect)
    recognizer = FaceRecognizer(config.sface_path)

    samples_dir = Path(args.samples)
    person_dirs = sorted(p for p in samples_dir.iterdir() if p.is_dir())

    total = 0
    correct = 0
    wrong: list[str] = []
    sims_correct: list[float] = []
    sims_wrong: list[float] = []
    started = time.time()

    for person_dir in person_dirs:
        name = person_dir.name.replace("_", " ")
        images = sorted(person_dir.glob("*.jpg"))
        if len(images) <= GALLERY_COUNT:
            continue

        gallery_imgs = images[:GALLERY_COUNT]
        test_imgs = images[GALLERY_COUNT:]

        # ---- 用前 4 张建库 ----
        index = GalleryIndex()
        for img_path in gallery_imgs:
            image = imread_unicode(img_path)
            if image is None:
                continue
            faces = detector.detect(image)
            if not faces:
                continue
            face = max(faces, key=lambda f: f.score)
            try:
                feat = recognizer.feature(image, face)
            except Exception:
                continue
            index.add(name, feat)

        if len(index) == 0:
            continue

        # ---- 用剩下的图测试 ----
        for img_path in test_imgs:
            image = imread_unicode(img_path)
            if image is None:
                continue
            faces = detector.detect(image)
            if not faces:
                total += 1
                wrong.append(f"{name}/{img_path.name}(无人脸)")
                continue

            face = max(faces, key=lambda f: f.score)
            try:
                feat = recognizer.feature(image, face)
            except Exception:
                total += 1
                wrong.append(f"{name}/{img_path.name}(特征失败)")
                continue

            match = index.match(feat)
            total += 1
            if match and match.similarity >= args.threshold:
                if match.name == name:
                    correct += 1
                    sims_correct.append(match.similarity)
                else:
                    wrong.append(
                        f"{name}/{img_path.name}→{match.name} {match.similarity:.0%}"
                    )
                    sims_wrong.append(match.similarity)
            else:
                sim = match.similarity if match else 0.0
                wrong.append(f"{name}/{img_path.name}(未过阈值 {sim:.0%})")
                sims_wrong.append(sim)

    elapsed = time.time() - started

    print("=" * 60)
    print(f"leave-one-out：{total} 张测试，{len(person_dirs)} 位名人")
    print(f"准确率：{correct}/{total} = {correct / max(total, 1):.1%}")
    if sims_correct:
        print(
            f"命中时平均相似度：{sum(sims_correct) / len(sims_correct):.1%}"
            f"（区间 {min(sims_correct):.1%} ~ {max(sims_correct):.1%}）"
        )
    if sims_wrong:
        print(f"未命中时平均相似度：{sum(sims_wrong) / len(sims_wrong):.1%}")
    print(f"耗时：{elapsed:.1f}s")

    if wrong:
        print("\n未命中明细（前 25 条）：")
        for w in wrong[:25]:
            print(f"  {w}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
