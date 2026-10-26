"""结果渲染：在原图上画人脸框与中文标签。

为什么用 PIL 而不是纯 OpenCV 画字
---------------------------------
``cv2.putText`` **不支持中文**（会画成乱码方块）。PIL 加载
``msyh.ttc``（微软雅黑）后可以正常渲染中文。

这也是本项目里「OpenCV 负责视觉、PIL 负责排版」分工的原因：
OpenCV 的中文字体支持一直很弱，硬塞只会更糟。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Windows 自带中文字体的候选路径
_FONT_CANDIDATES = (
    Path("C:/Windows/Fonts/msyh.ttc"),  # 微软雅黑
    Path("C:/Windows/Fonts/msyhbd.ttc"),  # 微软雅黑 Bold
    Path("C:/Windows/Fonts/simhei.ttf"),  # 黑体
    Path("C:/Windows/Fonts/simsun.ttc"),  # 宋体
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),  # Linux 兜底
)


@dataclass(frozen=True)
class LabelInfo:
    """画在框上方的标签内容。

    Attributes:
        title: 主标题（人名或「未识别」）。
        subtitle: 副标题（置信度等）。
        color: BGR 颜色。
    """

    title: str
    subtitle: str = ""
    color: tuple[int, int, int] = (60, 190, 60)


def load_font(size: int = 22) -> ImageFont.FreeTypeFont:
    """加载中文字体。

    Args:
        size: 字号。

    Returns:
        PIL 字体对象；找不到任何字体时退回 PIL 内置位图字体。
    """
    for path in _FONT_CANDIDATES:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size)
            except OSError:
                continue
    return ImageFont.load_default()


def write_image(path: Path, image: np.ndarray) -> None:
    """写图片，**兼容中文路径**。

    为什么不用 ``cv2.imwrite``
    ----------------------
    和 ``cv2.imread`` 一样，``cv2.imwrite`` 在 Windows 上用 C 的 ``fopen``
    打开文件，**非 ASCII 路径会写出一个乱码文件名**。

    实测：想写 ``示例_合影识别.jpg``，实际落盘的是
    ``绀轰緥_鍚堝奖璇嗗埆.jpg`` —— UTF-8 字节被按 GBK 解读。
    而且 ``cv2.imwrite`` **不报错**，返回 False 而已。

    解法：``cv2.imencode`` 编码到内存，再用 ``tofile`` 落盘
    —— ``tofile`` 走的是 Python 的文件 IO，路径编码由 Python 处理。

    Args:
        path: 输出路径。
        image: BGR 图像。

    Raises:
        OSError: 编码或写盘失败。
    """
    suffix = path.suffix or ".jpg"
    ok, buf = cv2.imencode(suffix, image)
    if not ok:
        raise OSError(f"图片编码失败：{path}")
    try:
        buf.tofile(str(path))
    except OSError as e:
        raise OSError(f"写入失败：{path}（{e}）") from e


def render(
    image: np.ndarray,
    boxes: list[tuple[int, int, int, int]],
    labels: list[LabelInfo],
    output_path: Path | None = None,
    font_size: int = 22,
) -> np.ndarray:
    """在图上画框和标签。

    Args:
        image: BGR 原图。
        boxes: 人脸框列表。
        labels: 与 boxes 一一对应的标签。
        output_path: 输出路径；None 则不写文件。
        font_size: 字体大小。

    Returns:
        绘制后的 BGR 图像。
    """
    if not boxes:
        result = image.copy()
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            write_image(output_path, result)
        return result

    # 先用 OpenCV 画框（线条抗锯齿在 PIL 里不好做）
    canvas = image.copy()
    for (x, y, w, h), label in zip(boxes, labels, strict=False):
        cv2.rectangle(
            canvas, (x, y), (x + w, y + h), label.color, max(2, w // 120)
        )

    # 再用 PIL 画中文标签
    pil_img = Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)
    font = load_font(font_size)

    # ---- 第一步：给每个标签找一个不打架的位置 ----
    # 每个标签有多个候选位置（框上方 / 框下方 / 框内侧 / 缩小字号后的上方），
    # 逐个试，第一个既在图内、又不和已放置的标签重叠的胜出。
    #
    # 不做碰撞检测会怎样？实测两张竖排的脸：上面那张的标签被迫放到框下方，
    # 正好压住下面那张的标签 —— 两段文字叠在一起，谁都看不清。
    occupied: list[tuple[int, int, int, int]] = []

    def _overlaps(rect: tuple[int, int, int, int]) -> bool:
        ax1, ay1, ax2, ay2 = rect
        for bx1, by1, bx2, by2 in occupied:
            if ax1 < bx2 and bx1 < ax2 and ay1 < by2 and by1 < ay2:
                return True
        return False

    for (x, y, _w, h), label in zip(boxes, labels, strict=False):
        text = label.title
        if label.subtitle:
            text = f"{label.title}  {label.subtitle}"

        small_font = load_font(max(14, font_size - 8))

        chosen: tuple[Any, int, int, int, int] | None = None
        for use_font in (font, small_font):
            left, top, right, bottom = draw.textbbox((0, 0), text, font=use_font)
            tw, th = right - left, bottom - top

            options = [
                (y - th - 12, y - th - 12 + th + 10),  # 框上方
                (y + h + 4, y + h + 4 + th + 10),  # 框下方
                (y, y + th + 10),  # 框内侧（兜底，会挡脸）
            ]
            for box_y1, box_y2 in options:
                if box_y1 < 0 or box_y2 > pil_img.height:
                    continue
                box_x2 = min(pil_img.width, x + tw + 16)
                if _overlaps((x, box_y1, box_x2, box_y2)):
                    continue
                chosen = (use_font, box_y1, box_x2, box_y2, tw)
                break
            if chosen is not None:
                break

        if chosen is None:
            # 全都放不下（重叠或越界）：退而求其次，用框内侧
            left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
            tw, th = right - left, bottom - top
            box_y1 = min(max(0, y), max(0, pil_img.height - th - 10))
            chosen = (font, box_y1, min(pil_img.width, x + tw + 16),
                      box_y1 + th + 10, tw)

        use_font, box_y1, box_x2, box_y2, _tw = chosen
        occupied.append((x, box_y1, box_x2, box_y2))

        # PIL 用 RGB，OpenCV 用 BGR，颜色要反过来
        fill = (label.color[2], label.color[1], label.color[0])
        draw.rectangle([(x, box_y1), (box_x2, box_y2)], fill=fill)
        draw.text(
            (x + 8, box_y1 + 5),
            text,
            fill=(255, 255, 255),
            font=use_font,
        )

    result = cv2.cvtColor(np.asarray(pil_img), cv2.COLOR_RGB2BGR)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        write_image(output_path, result)

    return result
