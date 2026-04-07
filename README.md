# 抖音短视频知识库 MVP

> 短视频文件 → 音频抽出 → 语音转写 → 结构化知识

**状态：** 最小链路已验证（本地 mp4 ✅），抖音分享链接下载待解决。

---

## 这个项目是什么

把抖音 / 本地短视频转成可搜索的知识库。

输入一个视频文件，得到一份带时间戳的文字记录，可以进一步做分段、向量检索、语义搜索。

---

## 现在已经能做什么

**✅ 验证通过（本地 mp4 链路）：**

```
mp4 文件
  → ffmpeg 抽出 16kHz WAV 音频
  → faster-whisper base 模型转写（带词级时间戳）
  → 结构化 JSON（metadata + transcript）
```

- 支持任意本地 mp4/mov/mkv
- 输出带秒级时间戳的转写 JSON
- 输出标准 metadata JSON（来源、路径、时长、模型信息）
- 全程离线运行（不需要网络）

---

## 现在还不能做什么

**❌ 抖音分享链接直接下载**  
抖音视频下载需要登录 cookies，`yt-dlp` 目前会报错 `Fresh cookies needed`。本地 mp4 路线不受影响，可以直接用。

**❌ 批量处理**  
目前一次只处理一个文件。

**❌ 前端页面 / Web UI**  
目前只有 CLI 脚本入口。

**❌ 搜索 / Chroma 向量库**  
下一步方向（见下方）。

---

## 为什么第一版先做本地 mp4

抖音视频下载需要登录态，依赖 `yt-dlp + cookies`，链路不稳定。本地 mp4 路线全程可复现、不依赖账号、不受抖音反爬限制。

先把核心的「音频→转写」链路验证通过，再处理抖音入口。

---

## 在本机跑起来

### 前置依赖

```bash
# ffmpeg（macOS）
brew install ffmpeg

# 或 Linux
sudo apt install ffmpeg
```

### 安装

```bash
git clone <repo-url>
cd short-video-brain-mvp
python3 -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

> **注意：** `faster-whisper` 会下载 Whisper 模型（约 74MB，base 模型）。首次运行会自动缓存到 `~/.cache/huggingface/`。

### 使用

```bash
# 本地 mp4（推荐）
python3 scripts/pipeline.py \
  --input /path/to/video.mp4 \
  --output-dir ./data

# 指定 Whisper 模型（默认 base）
python3 scripts/pipeline.py --input video.mp4 --output-dir ./data --model small
```

### 输出

```
data/
├── audio/           # 16kHz WAV
│   └── <hash>.wav
├── transcripts/     # 带时间戳转写 JSON
│   └── <hash>.json
└── meta/            # 标准元数据 JSON
    └── <hash>.meta.json
```

---

## 项目结构

```
short-video-brain-mvp/
├── app/                  # Web UI（未来阶段）
├── scripts/
│   └── pipeline.py      # 核心管线脚本
├── data/                 # 输出目录（gitignored）
│   ├── audio/
│   ├── transcripts/
│   └── meta/
├── docs/
│   ├── mvp-step1-report.md
│   ├── public-sample-output.md   # 样例输出说明
│   └── public-feedback-questions.md  # 反馈问题
├── requirements.txt
├── .gitignore
└── README.md
```

---

## 已知限制

| 功能 | 状态 | 说明 |
|------|------|------|
| 本地 mp4 转写 | ✅ 已验证 | 全链路可复现 |
| 抖音 URL 下载 | ❌ 受限 | 需登录 cookies |
| Whisper 模型选择 | ✅ 支持 | tiny/base/small/medium |
| 批量处理 | ❌ 未做 | 下一阶段 |
| Web UI | ❌ 未做 | 下一阶段 |
| 向量检索 | ❌ 未做 | 下一步方向 |

---

## 下一步已知方向

1. **音频分段（chunking）** — 按句子/段落合并 transcript segments，保留时间戳
2. **Chroma 向量数据库** — 建立可语义搜索的知识库
3. **抖音入口稳定化** — 评估 cookies 配置方案或 API 方案
4. **Web UI** — 简化搜索界面

---

## 反馈

如果你有兴趣参与这个项目，欢迎：
- 试用本地 mp4 链路，看转写质量
- 提供真实抖音视频的转写需求描述
- 讨论「抖音入口」的最优解法

具体反馈问题见 [docs/public-feedback-questions.md](docs/public-feedback-questions.md)。

---

## License

未选定。推荐考虑 MIT（最宽松）或 Apache-2.0（适合含模型的项目）。欢迎在 issue 中讨论。
