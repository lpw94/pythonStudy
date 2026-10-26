"""纯函数单元测试：不加载模型，跑得飞快。

这些测的是**不依赖模型的行为** —— 参数构造、边界处理、
格式转换。模型相关的集成测试在 test_integration.py。
"""

from __future__ import annotations

import numpy as np
import pytest

from celebrity_recognition.candidates import Candidate, load_candidates
from celebrity_recognition.clip_engine import cosine_similarity
from celebrity_recognition.detector import Face, crop_face
from celebrity_recognition.gallery import GalleryEntry, GalleryIndex
from celebrity_recognition.pipeline import imread_unicode


class TestLoadCandidates:
    """候选表加载。"""

    def test_builtin_not_empty(self) -> None:
        """内置表不能是空的。"""
        cands = load_candidates(builtin=True)
        assert len(cands) > 100

    def test_dedup_by_english_name(self) -> None:
        """英文名重复的只保留第一个。"""
        cands = load_candidates(builtin=True)
        names = [c.en for c in cands]
        assert len(names) == len(set(names))

    def test_no_blank_names(self) -> None:
        """不能有空的英文名（否则会占一个无意义的候选位）。"""
        for c in load_candidates(builtin=True):
            assert c.en.strip()
            assert "（" not in c.en
            assert "）" not in c.en

    def test_extra_file_parsed(self, tmp_path) -> None:
        """自定义文件按 ``中文名|英文名`` 解析。"""
        p = tmp_path / "c.txt"
        p.write_text("# 注释行\n测试甲|Test Alpha\nTest Beta\n\n", encoding="utf-8")
        cands = load_candidates(builtin=False, extra_path=p)
        assert len(cands) == 2
        assert cands[0].zh == "测试甲"
        assert cands[0].en == "Test Alpha"
        assert cands[1].zh == ""
        assert cands[1].en == "Test Beta"

    def test_extra_file_overrides_builtin_duplicate(self, tmp_path) -> None:
        """自定义条目与内置重名时，内置的先被占位。"""
        p = tmp_path / "c.txt"
        p.write_text("自定义|Xtomy\n", encoding="utf-8")
        cands = load_candidates(builtin=True, extra_path=p)
        # 内置里没有 Xtomy，所以它会被追加
        assert any(c.en == "Xtomy" for c in cands)

    def test_missing_extra_file_is_fine(self, tmp_path) -> None:
        """自定义文件不存在不应该报错。"""
        cands = load_candidates(builtin=True, extra_path=tmp_path / "nope.txt")
        assert len(cands) > 100


class TestCandidateDisplay:
    """展示名格式。"""

    def test_bilingual(self) -> None:
        """中英文都有时用括号形式。"""
        assert Candidate("汤姆", "Tom").display == "汤姆（Tom）"

    def test_same_name(self) -> None:
        """中英文相同时不重复显示。"""
        assert Candidate("Tom", "Tom").display == "Tom"

    def test_english_only(self) -> None:
        """只有英文名时直接显示。"""
        assert Candidate("", "Tom").display == "Tom"


class TestCandidateParse:
    """候选表的行解析。"""

    def test_bilingual(self) -> None:
        """``中文名|英文名``。"""
        c = Candidate.parse("成龙|Jackie Chan")
        assert c is not None
        assert c.zh == "成龙"
        assert c.en == "Jackie Chan"
        assert c.aliases == ()

    def test_with_aliases(self) -> None:
        """``中文名|英文名|别名1,别名2``。"""
        c = Candidate.parse("巨石强森|Dwayne Johnson|The Rock,The Rock 2")
        assert c is not None
        assert c.aliases == ("The Rock", "The Rock 2")

    def test_english_only(self) -> None:
        """只有英文名。"""
        c = Candidate.parse("Taylor Swift")
        assert c is not None
        assert c.zh == ""
        assert c.en == "Taylor Swift"

    def test_comment_ignored(self) -> None:
        """注释行返回 None。"""
        assert Candidate.parse("# 这是注释") is None
        assert Candidate.parse("   ") is None

    def test_missing_english_returns_none(self) -> None:
        """没有英文名无法匹配，返回 None。"""
        assert Candidate.parse("只有中文名|") is None

    def test_variants_includes_aliases(self) -> None:
        """variants 包含本名和所有别名。"""
        c = Candidate.parse("休·杰克曼|Hugh Jackman|Wolverine")
        assert c is not None
        assert c.variants == ("Hugh Jackman", "Wolverine")


class TestFaceToArray:
    """Face -> OpenCV 的 1×15 数组。"""

    def _face(self) -> Face:
        landmarks = np.array(
            [[10, 20], [30, 20], [20, 40], [5, 60], [35, 60]], dtype=np.float32
        )
        return Face(x=1, y=2, w=30, h=40, score=0.9, landmarks=landmarks)

    def test_shape(self) -> None:
        """必须是 1×15。"""
        assert self._face().to_array().shape == (1, 15)

    def test_layout(self) -> None:
        """前 4 个是 x/y/w/h，第 5~14 是关键点，最后是分数。"""
        arr = self._face().to_array()[0]
        assert arr[0] == 1
        assert arr[1] == 2
        assert arr[2] == 30
        assert arr[3] == 40
        assert arr[4] == 10
        assert arr[13] == 60
        assert arr[14] == pytest.approx(0.9)

    def test_center(self) -> None:
        """中心点计算正确。"""
        assert self._face().center == (1 + 15, 2 + 20)


class TestCropFace:
    """人脸裁剪。"""

    def _image(self) -> np.ndarray:
        return np.zeros((200, 200, 3), dtype=np.uint8)

    def test_padding_expands(self) -> None:
        """留白后裁剪区域变大。"""
        img = self._image()
        landmarks = np.zeros((5, 2), dtype=np.float32)
        face = Face(x=50, y=50, w=40, h=40, score=0.9, landmarks=landmarks)
        crop = crop_face(img, face, padding=0.5)
        # 40 * 0.5 = 20，理论上 80x80
        assert crop.shape[0] == 80
        assert crop.shape[1] == 80

    def test_no_padding(self) -> None:
        """padding=0 时就是原框。"""
        img = self._image()
        landmarks = np.zeros((5, 2), dtype=np.float32)
        face = Face(x=50, y=50, w=40, h=30, score=0.9, landmarks=landmarks)
        crop = crop_face(img, face, padding=0.0)
        assert crop.shape[:2] == (30, 40)

    def test_clips_at_border(self) -> None:
        """框贴边时不越界。"""
        img = self._image()
        landmarks = np.zeros((5, 2), dtype=np.float32)
        face = Face(x=0, y=0, w=40, h=40, score=0.9, landmarks=landmarks)
        crop = crop_face(img, face, padding=1.0)
        assert crop.shape[:2] == (80, 80)
        assert crop.shape[0] <= img.shape[0]
        assert crop.shape[1] <= img.shape[1]


class TestCosineSimilarity:
    """余弦相似度。"""

    def test_identical(self) -> None:
        """自身相似度为 1。"""
        v = np.array([1.0, 2.0, 3.0])
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal(self) -> None:
        """正交向量相似度为 0。"""
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 1.0])
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite(self) -> None:
        """相反向量相似度为 -1。"""
        a = np.array([1.0, 2.0])
        assert cosine_similarity(a, -a) == pytest.approx(-1.0)

    def test_empty(self) -> None:
        """空向量返回 0 而不是抛异常。"""
        assert cosine_similarity(np.array([]), np.array([1.0])) == 0.0

    def test_zero_vector(self) -> None:
        """零向量不除零。"""
        assert cosine_similarity(np.array([0.0, 0.0]), np.array([1.0, 1.0])) == 0.0


class TestGalleryIndex:
    """人脸特征库索引。"""

    def test_empty_match_returns_none(self) -> None:
        """空库匹配返回 None。"""
        assert GalleryIndex().match(np.array([1.0, 0.0])) is None

    def test_finds_correct_person(self) -> None:
        """特征一致时能找到对应的人。"""
        idx = GalleryIndex()
        idx.add("甲", np.array([1.0, 0.0, 0.0], dtype=np.float32))
        idx.add("乙", np.array([0.0, 1.0, 0.0], dtype=np.float32))
        match = idx.match(np.array([1.0, 0.0, 0.0], dtype=np.float32))
        assert match is not None
        assert match.name == "甲"
        assert match.similarity == pytest.approx(1.0)

    def test_names_dedup(self) -> None:
        """names 列表去重但保持顺序。"""
        idx = GalleryIndex(
            [
                GalleryEntry("甲", np.zeros(3, dtype=np.float32)),
                GalleryEntry("甲", np.zeros(3, dtype=np.float32)),
                GalleryEntry("乙", np.zeros(3, dtype=np.float32)),
            ]
        )
        assert idx.names == ["甲", "乙"]

    def test_zero_query(self) -> None:
        """零向量查询不崩。"""
        idx = GalleryIndex()
        idx.add("甲", np.array([1.0, 0.0], dtype=np.float32))
        assert idx.match(np.zeros(2, dtype=np.float32)) is None


class TestImreadUnicode:
    """中文路径读取。"""

    def test_missing_file(self, tmp_path) -> None:
        """文件不存在返回 None 而不是抛异常。"""
        assert imread_unicode(tmp_path / "没有这个.jpg") is None

    def test_reads_chinese_path(self, tmp_path) -> None:
        """中文路径能读出来（这是 imread_unicode 存在的理由）。"""
        import cv2

        img = np.zeros((40, 60, 3), dtype=np.uint8)
        img[:, :, 2] = 255  # 纯红，方便确认
        path = tmp_path / "中文名测试.jpg"
        cv2.imencode(".jpg", img)[1].tofile(str(path))

        loaded = imread_unicode(path)
        assert loaded is not None
        assert loaded.shape == (40, 60, 3)
        assert loaded[0, 0, 2] > 200

    def test_empty_file(self, tmp_path) -> None:
        """空文件返回 None。"""
        path = tmp_path / "empty.jpg"
        path.write_bytes(b"")
        assert imread_unicode(path) is None
