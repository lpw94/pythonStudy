"""CLIP 零样本名人分类引擎。

核心思路
--------
CLIP 有两个编码器：图像编码器和文本编码器。它们把图片和文字映射到
**同一个向量空间**。所以「这张脸是不是张三」这个问题，可以变成：
把图片编码成向量，和所有候选人名字的文本向量算余弦相似度，取最高分。

三个工程细节（决定了准确率）
------------------------------
1. **多 prompt 取最大值**
   单个 prompt（"a photo of X"）的判别力有限。对每个名字用多个模板
   （"a photo of X" / "X" / "a portrait of X" / "a photo of the actor X"），
   取该名字下**最高**的那个相似度 —— 相当于「最有利角度下这一票」。

2. **名字用英文**
   CLIP 的文本塔在英文图文对上训练，对英文人名的理解远好于中文名。
   中英文名都配，中文只用来显示。

3. **相似度而不是概率**
   CLIP 的原始 logits 经过 softmax 后在几百个候选上会被压得很平，
   0.3 和 0.25 之间的差别没有实际意义。所以这里用**归一化后的余弦相似度**
   （0~1）作为置信度，并把阈值设得比较保守（默认 0.18）。
   低于阈值一律判「不确定」，宁可说不知道，也不要瞎报一个名字。
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from celebrity_recognition.candidates import Candidate

# 每个名字使用的 prompt 模板。
# 「a photo of」是 CLIP 训练时最常见的图注形式，对人名的判别力最强。
PROMPT_TEMPLATES: tuple[str, ...] = (
    "a photo of {}",
    "a portrait photo of {}",
    "{}",
    "a photo of the celebrity {}",
)


class ClipNotAvailableError(RuntimeError):
    """CLIP 依赖或模型不可用。"""


@dataclass(frozen=True)
class Match:
    """一个候选结果。

    Attributes:
        candidate: 对应的名人。
        similarity: 归一化余弦相似度（0~1）。
    """

    candidate: Candidate
    similarity: float

    @property
    def display(self) -> str:
        """展示名。"""
        return self.candidate.display


class ClipEngine:
    """CLIP 零样本分类器。

    典型用法::

        engine = ClipEngine(CLIP_DIR, device="cuda")
        matches = engine.classify([crop1, crop2], candidates)
    """

    def __init__(
        self,
        model_dir: Path,
        device: str = "cpu",
        batch_size: int = 32,
    ) -> None:
        """加载 CLIP 模型。

        Args:
            model_dir: CLIP 模型目录（含 config.json 与权重）。
            device: 推理设备（``cuda`` / ``cpu``）。
            batch_size: 文本编码时的批大小。

        Raises:
            ClipNotAvailableError: 依赖缺失或模型文件不完整。
        """
        try:
            import torch
            from transformers import CLIPModel, CLIPProcessor
        except ImportError as e:  # pragma: no cover - 环境问题
            raise ClipNotAvailableError(
                "缺少 torch / transformers 依赖。\n"
                "请在 3.12 环境执行：\n"
                "  E:/workBuddy/pythonStudy/.py312/python.exe"
                " -m pip install torch transformers"
            ) from e

        if not model_dir.exists():
            raise ClipNotAvailableError(
                f"找不到 CLIP 模型目录：{model_dir}\n"
                f"请先运行 scripts/download_models.py。"
            )

        self._torch = torch
        self.device = device
        self.batch_size = batch_size
        self.fallback_reason: str | None = None
        # 候选表文本特征的缓存：key 是候选表的签名
        self._text_cache: dict[
            tuple[tuple[str, tuple[str, ...]], ...], tuple[np.ndarray, list[int]]
        ] = {}

        try:
            self.model = CLIPModel.from_pretrained(
                str(model_dir), use_safetensors=False
            ).to(device)
            self.processor = CLIPProcessor.from_pretrained(str(model_dir))
        except Exception as e:
            # CUDA OOM 是**常见情况**而非异常情况：Windows 是 WDDM 模式，
            # 显存由桌面程序（浏览器、ToDesk…）随时抢占，
            # 即使 nvidia-smi 显示还有 5GB 空闲，PyTorch 也可能分不到
            # 一块 20MB 的连续显存。生产代码必须能退回 CPU 而不是崩掉。
            if device != "cpu":
                self.fallback_reason = f"{type(e).__name__}: {e}"
                self.device = "cpu"
                torch.cuda.empty_cache()
                self.model = CLIPModel.from_pretrained(
                    str(model_dir), use_safetensors=False
                ).to("cpu")
                self.processor = CLIPProcessor.from_pretrained(str(model_dir))
            else:
                raise ClipNotAvailableError(f"加载 CLIP 模型失败：{e}") from e

        self.model.eval()

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    def _candidate_prompts(
        self, candidates: Sequence[Candidate]
    ) -> tuple[list[str], list[int]]:
        """为候选表生成 prompt 列表。

        每个候选会用**本名 + 所有别名**分别套上 prompt 模板，
        最终取该候选名下所有 prompt 的最高相似度。

        Args:
            candidates: 候选名人列表。

        Returns:
            (prompt 文本列表, 每条 prompt 归属的候选下标)。
        """
        texts: list[str] = []
        owner: list[int] = []
        for idx, cand in enumerate(candidates):
            for variant in cand.variants:
                for template in PROMPT_TEMPLATES:
                    texts.append(template.format(variant))
                    owner.append(idx)
        return texts, owner

    def _candidate_features(
        self, candidates: Sequence[Candidate]
    ) -> tuple[np.ndarray, list[int]]:
        """取候选表的文本特征，**带缓存**。

        为什么必须缓存
        --------------
        候选表是固定的，但每次识别都会重新编码上千条 prompt ——
        在 CPU 上这一项就要 1~2 秒，而一次识别可能只处理一张脸。
        缓存后第二次识别只做图像编码，快一个数量级。

        Args:
            candidates: 候选名人列表。

        Returns:
            (文本特征矩阵, 每行归属的候选下标)。
        """
        key = tuple((c.en, c.aliases) for c in candidates)
        cached = self._text_cache.get(key)
        if cached is not None:
            return cached

        texts, owner = self._candidate_prompts(candidates)
        feats = self._encode_texts(texts)
        self._text_cache[key] = (feats, owner)
        return feats, owner

    @staticmethod
    def _as_tensor(output: Any) -> Any:
        """把 ``get_*_features`` 的返回值统一成 tensor。

        transformers 4.x 返回裸 tensor，**5.x 改成了**
        ``BaseModelOutputWithPooling``（``pooler_output`` 才是投影后的特征）。
        直接 ``feats.norm(...)`` 在 5.x 上会报
        ``'BaseModelOutputWithPooling' object has no attribute 'norm'``。

        这里做一次兼容，两个大版本都能跑。
        """
        if hasattr(output, "pooler_output"):
            return output.pooler_output
        return output

    def _encode_texts(self, texts: Sequence[str]) -> np.ndarray:
        """把文本编码成归一化向量。

        Args:
            texts: 文本列表。

        Returns:
            形状 (len(texts), dim) 的 float32 数组，每行已 L2 归一化。
        """
        return self._encode(lambda device: self._encode_texts_on(texts, device))

    def _encode_texts_on(self, texts: Sequence[str], device: str) -> np.ndarray:
        """在指定设备上编码文本。"""
        torch = self._torch
        chunks: list[np.ndarray] = []

        with torch.no_grad():
            for i in range(0, len(texts), self.batch_size):
                batch = list(texts[i : i + self.batch_size])
                inputs = self.processor(
                    text=batch, return_tensors="pt", padding=True, truncation=True
                )
                inputs = {k: v.to(device) for k, v in inputs.items()}
                feats = self._as_tensor(self.model.get_text_features(**inputs))
                feats = feats / feats.norm(dim=-1, keepdim=True)
                chunks.append(feats.cpu().numpy().astype(np.float32))

        return np.concatenate(chunks, axis=0)

    def _encode_images(self, images: Sequence[np.ndarray]) -> np.ndarray:
        """把图片（BGR）编码成归一化向量。

        Args:
            images: BGR 图像列表。

        Returns:
            形状 (len(images), dim) 的 float32 数组，每行已 L2 归一化。
        """
        return self._encode(lambda device: self._encode_images_on(images, device))

    def _encode_images_on(
        self, images: Sequence[np.ndarray], device: str
    ) -> np.ndarray:
        """在指定设备上编码图片。"""
        torch = self._torch
        # CLIP 期望 RGB，OpenCV 读出来是 BGR。
        # ⚠️ 切片是**负 stride 的视图**，torch.from_numpy 不接受，
        #    必须 .copy() 变成连续内存，否则报
        #    "At least one stride in the given numpy array is negative"。
        rgb = [np.ascontiguousarray(img[:, :, ::-1]) for img in images]

        with torch.no_grad():
            inputs = self.processor(images=rgb, return_tensors="pt")
            pixel_values = inputs["pixel_values"].to(device)
            raw = self.model.get_image_features(pixel_values=pixel_values)
            feats = self._as_tensor(raw)
            feats = feats / feats.norm(dim=-1, keepdim=True)

        return feats.cpu().numpy().astype(np.float32)

    def _encode(self, fn: Callable[[str], np.ndarray]) -> np.ndarray:
        """在当前设备上执行编码，OOM 时退回 CPU 重试。

        推理阶段也可能 OOM：Windows 桌面程序随时会抢显存，
        而且**推理开始后显存占用比加载时更高**（激活值）。
        所以回退不能只做在加载阶段。

        Args:
            fn: 接收 device 参数的编码函数。

        Returns:
            编码结果。
        """
        try:
            return fn(self.device)
        except Exception as e:
            # 任何 CUDA 错误都退回 CPU —— 不只是 OOM。
            # 实测踩到过两类：
            #   ① CUDA out of memory（Windows 桌面程序抢显存）
            #   ② cudaErrorUnknown（Blackwell sm_120 + torch 2.11 的
            #      padding_mask 高级索引问题，图像编码正常、文本编码必崩）
            # 只判断 "out of memory" 会漏掉第二类，程序直接崩给用户看。
            message = str(e).lower()
            is_cuda_error = "cuda" in message or "accelerator" in message
            if self.device == "cpu" or not is_cuda_error:
                raise
            self.fallback_reason = f"{type(e).__name__}: {e}"
            self.device = "cpu"
            self._torch.cuda.empty_cache()
            return fn("cpu")

    # ------------------------------------------------------------------
    # 对外接口
    # ------------------------------------------------------------------
    def classify(
        self,
        images: Sequence[np.ndarray],
        candidates: Sequence[Candidate],
        top_k: int = 5,
    ) -> list[list[Match]]:
        """对每张图片给出 Top-K 候选。

        Args:
            images: 人脸裁剪图（BGR）。
            candidates: 候选名人列表。
            top_k: 每张图返回的候选数量。

        Returns:
            与 ``images`` 等长的结果列表，每个元素是按相似度降序的 Match 列表。

        Raises:
            ValueError: 输入为空。
        """
        if not images:
            raise ValueError("images 为空")
        if not candidates:
            raise ValueError("candidates 为空")

        text_feats, prompt_owner = self._candidate_features(candidates)
        image_feats = self._encode_images(images)

        # 相似度矩阵：(n_images, n_prompts)
        sims = image_feats @ text_feats.T

        results: list[list[Match]] = []
        for row in sims:
            best_per_candidate: dict[int, float] = {}
            for prompt_idx, score in enumerate(row):
                owner = prompt_owner[prompt_idx]
                value = float(score)
                if value > best_per_candidate.get(owner, -1.0):
                    best_per_candidate[owner] = value

            ranked = sorted(
                best_per_candidate.items(), key=lambda kv: kv[1], reverse=True
            )
            results.append(
                [
                    Match(candidates[cand_idx], score)
                    for cand_idx, score in ranked[:top_k]
                ]
            )

        return results

    def similarity_matrix(
        self,
        images: Sequence[np.ndarray],
        candidates: Sequence[Candidate],
    ) -> np.ndarray:
        """返回完整的 (n_images, n_candidates) 相似度矩阵。

        用途：需要自定义阈值策略时（比如「最高分与次高分拉开差距才算可信」）。

        Args:
            images: 人脸裁剪图（BGR）。
            candidates: 候选名人列表。

        Returns:
            float32 矩阵，每行对应一张图，每列对应一个候选。
        """
        if not images or not candidates:
            raise ValueError("images / candidates 不能为空")

        text_feats, prompt_owner = self._candidate_features(candidates)
        image_feats = self._encode_images(images)
        sims = image_feats @ text_feats.T

        out = np.full((len(images), len(candidates)), -1.0, dtype=np.float32)
        for prompt_idx in range(sims.shape[1]):
            owner = prompt_owner[prompt_idx]
            out[:, owner] = np.maximum(out[:, owner], sims[:, prompt_idx])
        return out


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """计算两个向量的余弦相似度。

    Args:
        a: 向量 a。
        b: 向量 b。

    Returns:
        余弦相似度；任一为向量时返回 0.0。
    """
    a = np.asarray(a, dtype=np.float32).ravel()
    b = np.asarray(b, dtype=np.float32).ravel()
    if a.size == 0 or b.size == 0:
        return 0.0
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def describe_engine(engine: ClipEngine) -> dict[str, Any]:
    """返回引擎信息，用于 CLI 打印。

    Args:
        engine: 引擎实例。

    Returns:
        描述字典。
    """
    return {
        "device": engine.device,
        "model": str(engine.model.config._name_or_path),
    }
