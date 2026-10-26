"""批量评估 CLIP 零样本的名人识别准确率。

用法::

    E:/workBuddy/pythonStudy/.py312/python.exe scripts/evaluate.py \
        --samples img/celebrity_samples

为什么需要这个脚本
------------------
「跑通一张图」证明不了什么 —— 一张图对了可能只是运气。
识别准确率是**必须用数据说话的**指标，所以这里对一批真实名人人脸
逐张跑 Top-1 命中，输出混淆情况。

**注意**：模型在同一个进程里加载一次，循环跑完全部图片 ——
每张图都重新加载 CLIP 要多花 35 秒，完全没必要。
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import defaultdict
from pathlib import Path

from celebrity_recognition.candidates import load_candidates
from celebrity_recognition.clip_engine import ClipEngine
from celebrity_recognition.detector import FaceDetector, crop_face
from celebrity_recognition.pipeline import imread_unicode


def main() -> int:
    """跑批量评估。

    Returns:
        退出码。
    """
    parser = argparse.ArgumentParser(description="评估名人识别准确率")
    parser.add_argument("--samples", required=True, help="样本目录")
    parser.add_argument("--device", default=None, help="cuda / cpu")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    from celebrity_recognition.config import get_config

    config = get_config()
    device = args.device or config.device

    detector = FaceDetector(config.yunet_path, config.detect)
    candidates = load_candidates(builtin=True, extra_path=config.candidates_path)
    engine = ClipEngine(config.clip_dir, device=device)

    samples_dir = Path(args.samples)
    person_dirs = sorted(p for p in samples_dir.iterdir() if p.is_dir())

    # 目录名 "Tom_Cruise" -> 期望名字 "Tom Cruise"
    # ⚠️ 但有些名字本身带标点（"Robert Downey Jr."），单纯把下划线换成空格
    #    会得到 "Robert Downey Jr" —— 与候选名差一个句点，
    #    导致**明明识别对了却算未命中**。必须显式处理这类别名。
    ALIASES = {
        "Robert Downey Jr": "Robert Downey Jr.",
        "Robert Downey Jr.": "Robert Downey Jr.",
    }

    def to_display(folder: str) -> str:
        name = folder.replace("_", " ")
        return ALIASES.get(name, name)

    total = 0
    top1 = 0
    top5 = 0
    miss_by_person: dict[str, list[str]] = defaultdict(list)
    scores: list[float] = []
    started = time.time()

    for person_dir in person_dirs:
        expected = to_display(person_dir.name)
        for img_path in sorted(person_dir.glob("*.jpg")):
            image = imread_unicode(img_path)
            if image is None:
                continue

            faces = detector.detect(image)
            if not faces:
                miss_by_person[expected].append(f"{img_path.name}(无人脸)")
                total += 1
                continue

            face = max(faces, key=lambda f: f.score)
            crop = crop_face(image, face, config.recognize.crop_padding)
            matches = engine.classify([crop], candidates, top_k=args.top_k)[0]

            total += 1
            if matches:
                scores.append(matches[0].similarity)
                names = [m.candidate.en for m in matches]
                if names[0] == expected:
                    top1 += 1
                if expected in names:
                    top5 += 1
                else:
                    miss_by_person[expected].append(
                        f"{img_path.name}→{matches[0].candidate.en}"
                        f" {matches[0].similarity:.0%}"
                    )

    elapsed = time.time() - started

    print("=" * 60)
    print(f"样本：{total} 张，{len(person_dirs)} 位名人")
    print(f"Top-1 准确率：{top1}/{total} = {top1 / total:.1%}")
    print(f"Top-5 准确率：{top5}/{total} = {top5 / total:.1%}")
    if scores:
        avg = sum(scores) / len(scores)
        print(f"Top-1 平均相似度：{avg:.1%}")
    print(f"耗时：{elapsed:.1f}s（{elapsed / max(total, 1):.2f}s/张）")

    print("\n按人统计（未命中详情）：")
    for name in sorted(miss_by_person):
        misses = miss_by_person[name]
        if misses:
            print(f"  {name}: {len(misses)} 张未命中")
            for m in misses:
                print(f"      {m}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
