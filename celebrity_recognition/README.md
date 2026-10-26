# celebrity-recognition · 名人明星识别

给一张图片，认出里面是谁。

**双引擎设计**：CLIP 零样本负责「像不像某个名人」，SFace 人脸特征库负责
「是不是这个人」。实测准确率分别是 **77.8%** 和 **99.1%** —— 两者不是替代
关系，而是「广度」与「精度」的分工。

```
图片 ──► YuNet 检测人脸 ──► 裁剪 ──┬─► CLIP 零样本 ──► 像谁（Top-K）
                                  └─► SFace 特征库 ──► 是谁（精确）
                                          │
                                    合并同一个人 ──► 输出标注图
```

---

## 快速开始

```bash
# 1. 下载模型（600MB+，不入版本库）
E:/workBuddy/pythonStudy/.py312/python.exe scripts/download_models.py

# 2. 识别
E:/workBuddy/pythonStudy/.py312/python.exe -m celebrity_recognition 图片.jpg

# 3. 指定输出与候选数
E:/workBuddy/pythonStudy/.py312/python.exe -m celebrity_recognition 图片.jpg \
    --top-k 3 --output out/结果.jpg
```

输出示例：

```
图片 512×512，检测到 3 张人脸，合并同一个人后是 2 个人（0 人未识别）

[1] 汤姆·克鲁斯（Tom Cruise）  置信度 84.9%  （来源：人脸库，合并了 1 张同脸）
    位置：x=51 y=29 w=149 h=200
    其它候选：汤姆·克鲁斯（Tom Cruise） 34%、杰森·贝特曼（Jason Bateman） 30%

[2] 艾玛·沃特森（Emma Watson）  置信度 65.7%  （来源：人脸库）
    位置：x=56 y=289 w=144 h=193
```

注意两个数字的区别：**「检测到 3 张脸」是原始检测数，「是 2 个人」是合并同一人之后的数**。
合影里同一个人出现两次只报一次，但检测数如实报出来。

> **为什么用 3.12 环境（`.py312`）而不是 3.13？**
> 本仓库的 `funeng_mqtt_sync` 需要 `opencv-python`（OpenCV 5 已移除 Haar
> 级联，改为 DNN），而 OpenCV 在 Windows 上的轮子覆盖到 3.12。
> 这个项目沿用同一个环境，避免装两套。

### 关于 GPU

**默认走 CPU。** 这不是保守，是实测结论：

本机 RTX 5060（Blackwell sm_120）+ `torch 2.11.0+cu128` 在 CLIP 的
**文本编码**路径上会抛 `cudaErrorUnknown` —— 报错点在
`transformers/masking_utils.py` 的 padding mask 高级索引。
图像编码正常，文本编码（batch 内长度不等、需要 padding）必崩。
cu128 索引里 torch 最高只到 2.11.0，没有更新的版本可换。

所以：

```bash
# 默认：CPU（可靠，实测 35s 加载 / 2.2s 每张）
python -m celebrity_recognition 图片.jpg

# 显式用 GPU；任何 CUDA 错误都会自动退回 CPU
python -m celebrity_recognition 图片.jpg --device cuda
```

自动降级覆盖两类错误：**显存不足**（Windows 桌面程序随时抢显存，
即使 nvidia-smi 显示还有 5GB 空闲也可能分不到一块 20MB 的连续显存）
和**其它 CUDA 错误**。降级后会打印警告，实际用的设备也会如实报出来。

如果你的环境没有这个问题，可以设 `CELEB_DEVICE=cuda` 让它默认走 GPU。

---

## 两个引擎，实测数据

用 `celebrity-1000` 数据集（997 位名人、18184 张图）里 18 位名人的
180 张人脸图做的评估：

| 引擎 | 评估方式 | Top-1 | Top-5 | 耗时 | 说明 |
|------|---------|-------|-------|------|------|
| **CLIP 零样本** | 180 张直接分类 | **90.0%** | **98.9%** | 0.11 s/张 | 不需要建库，候选 1132 位 |
| **SFace 特征库** | leave-one-out（每人 4 张建库、6 张测试） | **99.1%**（107/108） | — | 0.02 s/张 | 需要参考图，但更快 |

两个数字要这么读：

- CLIP 的 90.0% 是在**「这人在不在候选表里」**的前提下测的。
  不在表里的人，CLIP 只能给一个「像某个陌生人」的答案 ——
  **候选表的覆盖度就是它的天花板**（下面第 10 条坑有实测数据）。
- 人脸库的 99.1% 是 **leave-one-out** —— 用这个人的**其它**图建库、
  用没见过的图去测。同图建库同图测的准确率会接近 100%，但那只是记住了
  这张图，没有意义。

**结论**：想要「随便一张明星剧照都能给个候选」→ 用 CLIP；
想要「确定是不是这个人」→ 建库。

### 准确率是怎么一步步提上去的

| 阶段 | Top-1 | 关键改动 |
|------|-------|---------|
| 初版 | 77.8% | 候选表 192 位，有几条英文名是瞎写的 |
| 修掉错条目 + 修评估脚本 | 82.2% | `AlGdna` 这类错条目在**抢**匹配；评估脚本的目录名映射有 bug |
| **候选表扩到 1132 位** | **90.0%** | 三位名人各 10 张图全错的根因是**不在候选表里** |
| 加别名（`The Rock` 等） | — | 70 条别名，取本名/别名里的最高分 |

---

## 怎么用好它

### 1. 扩展候选表

内置 192 位精选（华语 + 港台 + 日韩 + 好莱坞 + 体育，带中文名），
加上 `data/candidates.txt` 里的 997 位（从 celebrity-1000 导出），
**合计 1132 位**。

想加自己的，追加到 `models/candidates.txt`，每行一个：

```text
# 中文名|英文名|别名1,别名2（可选）
刘德华|Andy Lau
新海诚|Makoto Shinkai
巨石强森|Dwayne Johnson|The Rock
```

**为什么要英文名**：CLIP 的文本塔在英文图文对上训练。`"成龙"`在它的世界里
几乎没有对应，`"Jackie Chan"`则非常强。所以匹配用英文名，中文名纯粹给人看。

**为什么要别名**：CLIP 对明星的认知来自网络图文对，而网络上**艺名和角色名**
的出现频率远高于本名 —— 它认「The Rock」「Wolverine」「Hermione Granger」。
同一个候选的所有表述取最高分即可。

（实测：候选表里混进几个我瞎写的英文名后，它**主动抢走了**真实名人的
匹配 —— 一个叫 `AlGdna` 的错条目把 Mila Kunis 的 5 张图全吸走了。）

### 2. 建人脸特征库

```
models/gallery/
  成龙/
    01.jpg
    02.jpg
  迪丽热巴/
    01.jpg
```

目录名就是人名，不需要理解任何格式。然后：

```bash
E:/workBuddy/pythonStudy/.py312/python.exe -m celebrity_recognition --build-gallery
```

建库后**自动优先使用**人脸库结果（比 CLIP 可靠），置信度不过阈值才回落
到 CLIP。

---

## 目录结构

```
celebrity_recognition/
├── src/celebrity_recognition/
│   ├── config.py        路径、阈值、设备选择
│   ├── candidates.py    候选名人表（中英对照，192 位）
│   ├── detector.py      YuNet 人脸检测（OpenCV DNN）
│   ├── clip_engine.py   CLIP 零样本分类
│   ├── gallery.py       SFace 人脸特征库
│   ├── pipeline.py      流程编排（检测 → 识别 → 合并）
│   ├── render.py        标注图渲染（OpenCV 画框 + PIL 画中文）
│   └── cli.py           命令行入口
├── scripts/
│   ├── download_models.py          下载三个模型
│   ├── export_dataset_candidates.py 从 celebrity-1000 导出全量候选表
│   ├── extract_samples.py          从 celebrity-1000 导出测试素材
│   ├── evaluate.py                 CLIP 零样本批量评估
│   ├── evaluate_gallery.py         人脸库 leave-one-out 评估
│   └── make_group_photo.py         生成多人合影（测多脸与合并）
├── data/
│   └── candidates.txt              997 位名人的全量候选表（进版本库）
├── models/              模型与素材（gitignore）
├── tests/               单测 + 集成测试
└── out/                 标注图输出（gitignore）
```

---

## 实测踩过的坑

### 1. `cv2.imread` 读不了中文路径

```python
cv2.imread("图片/中文名.jpg")   # → None，而且不报错
```

`cv2.imread` 内部用 C 的 `fopen`，在 Windows 上无法处理非 ASCII 路径。
代码看着完全正常，结果就是读不出图。

**解法**：`np.fromfile` 读字节 + `cv2.imdecode` 解码，绕开文件系统编码。

### 2. `cv2.CascadeClassifier` 在 OpenCV 5 被移除

Haar 级联在 4.x 已逐步废弃，**OpenCV 5.0 直接移除了**。本项目改用
DNN 版 YuNet（228KB，OpenCV 自带 `FaceDetectorYN`）。

### 3. `alignCrop` 的第二个参数必须是 numpy 数组

```python
recognizer.alignCrop(image, face_obj)
# → (-5:Bad argument) ... face_box is not a numpy array, neither a scalar
```

`cv2.FaceRecognizerSF.alignCrop` 要的是 **1×15 的 numpy 数组**
（x, y, w, h + 5 个关键点 + score），传自定义 dataclass 会直接报参数错误。
`Face.to_array()` 就是干这个的。

### 4. transformers 5.x 的 `get_text_features` 不再返回 tensor

```python
feats = model.get_text_features(**inputs)
feats.norm(...)   # 5.x: AttributeError: 'BaseModelOutputWithPooling' has no 'norm'
```

4.x 返回裸 tensor，**5.x 改成了 `BaseModelOutputWithPooling`**，
要取 `.pooler_output`。`ClipEngine._as_tensor()` 做了兼容，两个大版本都能跑。

### 5. BGR→RGB 的切片是负 stride

```python
rgb = img[:, :, ::-1]                    # 视图，stride 为负
torch.from_numpy(rgb)                    # → ValueError: negative strides
```

必须 `np.ascontiguousarray(...)` 变成连续内存。

### 6. `cv2.putText` 画不了中文

会画成乱码方块。本项目用 OpenCV 画框、PIL 加载 `msyh.ttc` 画中文标签。

### 7. 一个自己写错的判定差点毁掉人脸库评估

最初 `alignCrop` 传错类型，异常被 `except` 吞掉，导致**建库全部失败但
评估脚本报告「0 张测试、准确率 0%」** —— 静默失败比崩溃更难查。
现在建库失败会明确报出来。

### 8. 目录名直接当人名，两种引擎的输出格式对不上

人脸库用目录名（`Tom_Cruise`）当人名，CLIP 用「中文名（英文名）」。
同一次识别里混排两种格式很难看。修法：建库时把 `_` 还原成空格，
人脸库命中后再去候选表里查一次，统一成 `汤姆·克鲁斯（Tom Cruise）`。

### 9. 报错信息为空，等于什么都没说

CUDA 的 `AcceleratorError` 的 `str(e)` 可能是空字符串，
CLI 只打印 `初始化失败：` 等于零信息。现在会打印异常类型 + 完整堆栈。

### 10. 认不出的名人，多半不在候选表里

第一版评估 77.8%，有三个人各 10 张图**全部**失败：

```
Dwayne Johnson → Jason Statham / Kobe Bryant
Hugh Jackman  → Ben Affleck
Mila Kunis    → Katy Perry
```

一开始我以为是「CLIP 认识艺名不認識本名」，去加别名。
**实测才看清根因：这三人压根就不在候选表里** —— 192 人的候选表没有他们，
模型只能在剩下的人里找 closest，自然给出一堆「像某某」。

把这三人加进候选表，立刻全部正确识别（32% / 33% / 24%）。
再把候选表扩到 1132 位，整体 Top-1 从 82.2% 涨到 **90.0%**。

**教训**：零样本模型的准确率瓶颈往往不在模型，而在**你给它的候选空间**。
先确认「正确答案在不在表里」，再谈调 prompt、换模型。

### 11. 每次识别都重编码上千条 prompt，慢 18 倍

候选表的文本特征是固定的，却在每次 `classify()` 里重算一遍。
180 张图 = 180 × 4528 条 prompt = **80 万次文本编码**。

加了个按候选表签名（`(英文名, 别名)` 元组）做 key 的缓存，
第二次起直接复用。评估耗时从 **351.6s 降到 19.4s**（0.11s/张）。

**教训**：固定输入的预计算就该缓存。这不是优化技巧，是基本功。

---

## 网络前提（本机实测）

| 源 | 状态 | 用途 |
|---|---|---|
| `pypi.org` | ✅ 通 | pip 装包 |
| `hf-mirror.com` | ✅ 通 | CLIP 模型（`huggingface.co` **不通**） |
| `media.githubusercontent.com` | ✅ 通 | opencv_zoo 的 LFS 模型（`raw.githubusercontent.com` **不通**） |
| `download.pytorch.org` | ✅ 通 | CUDA 版 torch |
| `huggingface.co` | ❌ 不通 | — |
| `raw.githubusercontent.com` | ❌ 不通 | — |

```bash
# CUDA 版 torch（RTX 5060 是 Blackwell，需要 cu128）
E:/workBuddy/pythonStudy/.py312/python.exe -m pip install torch \
    --index-url https://download.pytorch.org/whl/cu128
```

⚠️ `pip install torch` **不会**自动换成本地版本后缀的 cu128 包 ——
必须先 `pip uninstall torch` 再装。

---

## 测试

```bash
E:/workBuddy/pythonStudy/.py312/python.exe -m pytest tests -q
E:/workBuddy/pythonStudy/.py312/python.exe -m ruff check src tests scripts
```

集成测试需要素材（`img/celebrity_samples/`），缺失时自动跳过。

---

## 已知限制

- **CLIP 零样本不是身份认定**。它回答「像谁」，不回答「是谁」。
  真要确认身份，用人脸库引擎。
- **候选表决定 CLIP 的天花板**。人不在表里，就只能给陌生人。
- **SFace 跨库泛化有限**。它在 VGGFace2 上训练，中东/东亚面孔的
  特征区分度会弱一些；同一人的不同年龄、妆造差别大时也可能匹配失败。
- **检测会漏脸**。YuNet 对某些角度/表情不给响应 —— 实测一张 Messi 的
  侧脸单独看能检出（0.93），和别的脸拼成 2×2 网格后反而检不出，
  阈值降到 0.3 也没用。降低 `DetectConfig.score_threshold` 能捞回一些，
  但也会引入误检。
- **不做活体检测**。给一张打印照片同样能识别，这是识别，不是认证。
