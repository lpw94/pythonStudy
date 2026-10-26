"""集成测试：真的加载模型，跑完整流程。

比单测慢（模型加载要几十秒），所以整个模块只加载一次，
用 ``pytest.fixture(scope="module")`` 共享。

素材依赖：``img/celebrity_samples/``（由 ``scripts/extract_samples.py`` 导出）。
素材不在时自动跳过，不让测试因为缺数据而红。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from celebrity_recognition.config import get_config
from celebrity_recognition.detector import FaceDetector
from celebrity_recognition.pipeline import Recognizer, format_report

SAMPLES_DIR = Path(__file__).resolve().parents[1] / "img/celebrity_samples"

pytestmark = pytest.mark.skipif(
    not SAMPLES_DIR.exists(),
    reason="缺少测试素材：先运行 scripts/extract_samples.py",
)


@pytest.fixture(scope="module")
def config():
    """应用配置。"""
    return get_config()


@pytest.fixture(scope="module")
def recognizer(config):
    """识别器（整个模块共用，只加载一次模型）。"""
    return Recognizer(config=config, device="cpu")


class TestDetect:
    """人脸检测。"""

    def test_detects_face_in_sample(self, config) -> None:
        """样本图里能检测到人脸。"""
        from celebrity_recognition.detector import FaceDetector

        detector = FaceDetector(config.yunet_path, config.detect)
        img_path = SAMPLES_DIR / "Tom_Cruise" / "01.jpg"
        if not img_path.exists():
            pytest.skip("样本不存在")

        from celebrity_recognition.pipeline import imread_unicode

        image = imread_unicode(img_path)
        faces = detector.detect(image)
        assert len(faces) >= 1
        assert faces[0].score > 0.5


class TestCandidateCoverage:
    """候选表覆盖度 —— CLIP 的天花板。"""

    def test_dataset_candidates_loaded(self) -> None:
        """全量候选表被加载进来了（否则 CLIP 认不出不在表里的人）。"""
        from celebrity_recognition.candidates import load_candidates

        cands = load_candidates(builtin=True, extra_path=get_config().candidates_path)
        assert len(cands) > 500, "候选表覆盖度不足"

    def test_hard_cases_are_covered(self) -> None:
        """实测踩过坑的三个人必须在候选表里。

        这三人各 10 张图曾全部识别失败（被认成 Jason Statham /
        Ben Affleck / Katy Perry），根因是**不在候选表里**。
        """
        from celebrity_recognition.candidates import load_candidates

        cands = load_candidates(builtin=True, extra_path=get_config().candidates_path)
        names = {c.en for c in cands}
        for who in ("Dwayne Johnson", "Hugh Jackman", "Mila Kunis"):
            assert who in names, f"{who} 不在候选表里"

    def test_alias_participates_in_matching(self) -> None:
        """别名能提高命中率（CLIP 认识「The Rock」而不是本名）。"""
        from celebrity_recognition.candidates import Candidate
        from celebrity_recognition.clip_engine import ClipEngine
        from celebrity_recognition.detector import crop_face
        from celebrity_recognition.pipeline import imread_unicode

        img_path = SAMPLES_DIR / "Dwayne_Johnson" / "05.jpg"
        if not img_path.exists():
            pytest.skip("样本不存在")

        config = get_config()
        engine = ClipEngine(config.clip_dir, device="cpu")
        detector = FaceDetector(config.yunet_path, config.detect)

        image = imread_unicode(img_path)
        faces = detector.detect(image)
        crop = crop_face(image, faces[0], config.recognize.crop_padding)

        # 只用本名
        plain = engine.classify(
            [crop], [Candidate("德韦恩", "Dwayne Johnson")], top_k=1
        )[0]
        # 本名 + 别名
        with_alias = engine.classify(
            [crop],
            [Candidate("德韦恩", "Dwayne Johnson", aliases=("The Rock",))],
            top_k=1,
        )[0]

        # 加了别名不应该让正确答案是「更差」的
        assert with_alias[0].similarity >= plain[0].similarity - 1e-6


class TestTextFeatureCache:
    """候选表文本特征的缓存。"""

    def test_same_candidates_reuse_features(self) -> None:
        """同一批候选第二次调用不重新编码。"""
        from celebrity_recognition.candidates import load_candidates
        from celebrity_recognition.clip_engine import ClipEngine

        config = get_config()
        engine = ClipEngine(config.clip_dir, device="cpu")
        cands = load_candidates(builtin=True, extra_path=config.candidates_path)

        assert len(engine._text_cache) == 0
        engine._candidate_features(cands)
        assert len(engine._text_cache) == 1
        engine._candidate_features(cands)
        assert len(engine._text_cache) == 1, "缓存没有生效"


class TestRecognize:
    """完整识别流程。"""

    def test_identifies_known_person(self, recognizer) -> None:
        """库里的人应该被认出来。"""
        img_path = SAMPLES_DIR / "Tom_Cruise" / "05.jpg"
        if not img_path.exists():
            pytest.skip("样本不存在")

        result, image = recognizer.recognize(img_path)
        assert result.face_count >= 1

        names = [r.name for r in result.results]
        assert any("Tom Cruise" in n for n in names), f"未认出，实际：{names}"

    def test_result_is_json_serializable(self, recognizer) -> None:
        """结果能直接转 JSON。"""
        import json

        img_path = SAMPLES_DIR / "Emma_Watson" / "05.jpg"
        if not img_path.exists():
            pytest.skip("样本不存在")

        result, _ = recognizer.recognize(img_path)
        payload = json.dumps(result.to_dict(), ensure_ascii=False)
        assert "faces" in payload

    def test_report_format(self, recognizer) -> None:
        """文字报告可读。"""
        img_path = SAMPLES_DIR / "Brad_Pitt" / "05.jpg"
        if not img_path.exists():
            pytest.skip("样本不存在")

        result, _ = recognizer.recognize(img_path)
        report = format_report(result)
        assert "检测到" in report

    def test_render_produces_image(self, recognizer, tmp_path) -> None:
        """能画出标注图。"""
        import cv2

        img_path = SAMPLES_DIR / "Tom_Cruise" / "05.jpg"
        if not img_path.exists():
            pytest.skip("样本不存在")

        result, image = recognizer.recognize(img_path)
        out = tmp_path / "annotated.jpg"
        rendered = recognizer.render_result(result, image, output_path=out)

        assert rendered.shape == image.shape
        assert out.exists()
        assert cv2.imread(str(out)) is not None

    def test_render_to_chinese_filename(self, recognizer, tmp_path) -> None:
        """**中文文件名不能乱码**。

        ``cv2.imwrite`` 在 Windows 上会把 ``示例.jpg`` 写成
        ``绀轰緥.jpg``（UTF-8 被按 GBK 解读），而且不报错。
        这是踩过的真实坑，必须有回归测试。
        """
        from celebrity_recognition.pipeline import imread_unicode

        img_path = SAMPLES_DIR / "Tom_Cruise" / "05.jpg"
        if not img_path.exists():
            pytest.skip("样本不存在")

        result, image = recognizer.recognize(img_path)
        out = tmp_path / "示例_合影识别.jpg"
        recognizer.render_result(result, image, output_path=out)

        assert out.exists(), "中文文件名没有生成"
        # 文件名必须原样保留，不能变成乱码
        assert out.name == "示例_合影识别.jpg"
        # 且图片内容能读回来
        assert imread_unicode(out) is not None
