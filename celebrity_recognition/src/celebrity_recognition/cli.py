"""命令行入口：给一张图，认出里面的人。

用法::

    python -m celebrity_recognition 图片路径
    python -m celebrity_recognition 图片路径 --output 结果.jpg
    python -m celebrity_recognition 图片路径 --json
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

from celebrity_recognition.config import get_config
from celebrity_recognition.pipeline import Recognizer, format_report


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。

    Returns:
        解析器。
    """
    parser = argparse.ArgumentParser(
        prog="celebrity_recognition",
        description="给一张图片，识别里面的名人明星",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m celebrity_recognition photo.jpg
  python -m celebrity_recognition photo.jpg --top-k 3 --output out/result.jpg
  python -m celebrity_recognition photo.jpg --json
  python -m celebrity_recognition --build-gallery
""",
    )
    parser.add_argument("image", nargs="?", help="图片路径")
    parser.add_argument(
        "--output", "-o", help="标注图输出路径（默认写到 out/ 目录）"
    )
    parser.add_argument(
        "--no-render", action="store_true", help="只输出文字结果，不生成标注图"
    )
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    parser.add_argument(
        "--top-k", type=int, default=None, help="每张脸返回的候选数量（默认 5）"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="CLIP 置信度阈值（默认 0.18），调高更保守",
    )
    parser.add_argument(
        "--gallery", help="人脸特征库目录（默认 models/gallery）"
    )
    parser.add_argument(
        "--no-gallery", action="store_true", help="禁用人脸特征库，只用 CLIP"
    )
    parser.add_argument(
        "--candidates", help="自定义候选表文件（每行 中文名|英文名）"
    )
    parser.add_argument(
        "--device", choices=["cuda", "cpu"], help="推理设备（默认自动选）"
    )
    parser.add_argument(
        "--build-gallery",
        action="store_true",
        help="只建立人脸特征库索引（不识别图片）",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="打印更多过程信息")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 主函数。

    Args:
        argv: 参数列表，None 表示读 sys.argv。

    Returns:
        进程退出码：0 成功，1 出错，2 参数错误。
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    config = get_config()

    # 命令行覆盖配置文件
    if args.gallery:
        config = config.__class__(
            detect=config.detect,
            recognize=config.recognize,
            models_dir=config.models_dir,
            clip_dir=config.clip_dir,
            yunet_path=config.yunet_path,
            sface_path=config.sface_path,
            candidates_path=(
                Path(args.candidates) if args.candidates else config.candidates_path
            ),
            gallery_dir=Path(args.gallery),
            output_dir=config.output_dir,
        )
    elif args.candidates:
        config = config.__class__(
            detect=config.detect,
            recognize=config.recognize,
            models_dir=config.models_dir,
            clip_dir=config.clip_dir,
            yunet_path=config.yunet_path,
            sface_path=config.sface_path,
            candidates_path=Path(args.candidates),
            gallery_dir=config.gallery_dir,
            output_dir=config.output_dir,
        )

    if args.threshold is not None:
        config = config.__class__(
            detect=config.detect,
            recognize=config.recognize.__class__(
                min_similarity=args.threshold,
                top_k=config.recognize.top_k,
                crop_padding=config.recognize.crop_padding,
                merge_similarity=config.recognize.merge_similarity,
            ),
            models_dir=config.models_dir,
            clip_dir=config.clip_dir,
            yunet_path=config.yunet_path,
            sface_path=config.sface_path,
            candidates_path=config.candidates_path,
            gallery_dir=config.gallery_dir,
            output_dir=config.output_dir,
        )

    # ---------------- 只建库 ----------------
    if args.build_gallery:
        from celebrity_recognition.detector import FaceDetector
        from celebrity_recognition.gallery import FaceRecognizer, build_gallery

        if not config.gallery_dir.exists():
            print(f"人脸库目录不存在：{config.gallery_dir}")
            print("请按下面的结构放置参考图：")
            print("  gallery/成龙/01.jpg")
            print("  gallery/迪丽热巴/01.jpg")
            return 2

        detector = FaceDetector(config.yunet_path, config.detect)
        recognizer = FaceRecognizer(config.sface_path)
        index = build_gallery(
            config.gallery_dir, detector, recognizer, verbose=True
        )
        print(f"\n共 {len(index.names)} 位名人，{len(index)} 条特征")
        return 0

    # ---------------- 必须给图片 ----------------
    if not args.image:
        parser.print_help()
        return 2

    image_path = Path(args.image)
    if not image_path.exists():
        print(f"图片不存在：{image_path}")
        return 2

    try:
        recognizer = Recognizer(
            config=config,
            device=args.device,
            use_gallery=not args.no_gallery,
        )
    except Exception as e:
        # 打印完整堆栈：CUDA OOM 这类异常的 str(e) 可能是空的，
        # 只打一行「初始化失败：」等于什么都没说
        print(f"初始化失败：{e or type(e).__name__}")
        traceback.print_exc()
        return 1

    if args.verbose:
        print(f"推理设备：{recognizer.clip.device}")
        print(f"候选名人：{len(recognizer.candidates)} 位")
        print(f"人脸库：{'已启用' if recognizer.gallery else '未启用'}")
        if recognizer.clip.fallback_reason:
            print("⚠️ 显存不足，已退回 CPU 推理（速度会明显变慢）")
        print()

    try:
        result, image = recognizer.recognize(image_path, top_k=args.top_k)
    except FileNotFoundError as e:
        print(str(e))
        return 1

    # 输出标注图
    output_path: Path | None = None
    if not args.no_render:
        if args.output:
            output_path = Path(args.output)
        else:
            output_path = config.output_dir / f"识别_{image_path.stem}.jpg"
        recognizer.render_result(result, image, output_path=output_path)

    if args.json:
        payload = result.to_dict()
        if output_path:
            payload["output"] = str(output_path)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_report(result))
        if output_path:
            print(f"\n标注图：{output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
