# video-rag

Turn downloaded videos into timestamped, LLM-ready knowledge artifacts.

把已下载的视频文件转成带时间戳、适合后续 RAG/LLM 工作流使用的结构化知识材料。

![CLI demo](docs/assets/cli-demo.svg)

## What it does

- Accepts downloaded local video files such as `.mp4`, `.mov`, and `.mkv`
- Extracts 16kHz mono WAV audio with `ffmpeg`
- Transcribes speech with `faster-whisper`
- Writes transcript JSON and metadata JSON for downstream processing

## 它能做什么

- 接收已经下载到本地的视频文件，例如 `.mp4`、`.mov`、`.mkv`
- 使用 `ffmpeg` 抽取 16kHz 单声道音频
- 使用 `faster-whisper` 进行语音转写
- 输出 transcript JSON 和 metadata JSON，方便后续做检索、摘要和知识整理

## Why it matters for LLM workflows

Most video knowledge is trapped inside audio. `video-rag` focuses on the first reliable step: turning downloaded videos into inspectable text artifacts that can later be chunked, indexed, retrieved, summarized, or injected into prompts.

This release is intentionally narrow. It does not pretend to be a full RAG product yet. It gives you a clean ingestion foundation.

## 为什么对 LLM 工作流有价值

大量视频里的有效信息，其实都被困在音频里。`video-rag` 先把最可靠的第一步做好：把已经下载的视频，转成可检查、可复用、可继续加工的文本材料。

这一版不会假装自己已经是完整的 RAG 产品。它更像一条干净、稳定的前置处理管线，为后续 chunking、索引、检索、摘要和提示词上下文构建打基础。

## Demo output

The current public demo takes one downloaded local video file and produces:

- `data/audio/<job_id>.wav`
- `data/transcripts/<job_id>.json`
- `data/meta/<job_id>.meta.json`

See the sample output:

- [docs/public-sample-output.md](docs/public-sample-output.md)

## 示例输出

当前公开演示使用一段已经下载到本地的视频作为输入，输出三类文件：

- `data/audio/<job_id>.wav`
- `data/transcripts/<job_id>.json`
- `data/meta/<job_id>.meta.json`

具体样例可见：

- [docs/public-sample-output.md](docs/public-sample-output.md)

## Quickstart

### Requirements

- Python 3.9+
- `ffmpeg`

Install `ffmpeg`:

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg
```

### Setup

```bash
git clone https://github.com/Jia-Ethan/video-rag.git
cd video-rag
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Run

```bash
python3 scripts/pipeline.py \
  --input /path/to/downloaded-video.mp4 \
  --output-dir ./data
```

Optional model selection:

```bash
python3 scripts/pipeline.py \
  --input /path/to/downloaded-video.mp4 \
  --output-dir ./data \
  --model small
```

## 快速开始

### 依赖

- Python 3.9+
- `ffmpeg`

安装 `ffmpeg`：

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg
```

### 安装

```bash
git clone https://github.com/Jia-Ethan/video-rag.git
cd video-rag
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 运行

```bash
python3 scripts/pipeline.py \
  --input /path/to/downloaded-video.mp4 \
  --output-dir ./data
```

可选模型参数：

```bash
python3 scripts/pipeline.py \
  --input /path/to/downloaded-video.mp4 \
  --output-dir ./data \
  --model small
```

## Supported input

- Downloaded local video files only
- Recommended formats: `.mp4`, `.mov`, `.mkv`

## 当前支持的输入

- 只支持已经下载到本地的视频文件
- 推荐格式：`.mp4`、`.mov`、`.mkv`

## Current limitations

- URL inputs are not supported in this release
- No chunking, vector store, retrieval UI, or Web app yet
- No batch ingestion yet

## 当前边界

- 这一版不支持任何 URL 输入
- 这一版还没有 chunking、向量库、检索界面和 Web UI
- 这一版还不支持批量处理

## Roadmap

1. Add chunk-ready transcript output for downstream retrieval
2. Add a minimal retrieval layer so the “RAG” part becomes directly demoable
3. Improve artifact quality and structure for longer video workflows

## 路线图

1. 增加面向后续检索的 chunk-ready 输出
2. 增加最小可演示的 retrieval 层，让 “RAG” 更名副其实
3. 优化更长视频场景下的输出质量和结构

## Feedback

If you are building video knowledge workflows and want to talk, I would love to hear from you.

- GitHub Discussions: [github.com/Jia-Ethan/video-rag/discussions](https://github.com/Jia-Ethan/video-rag/discussions)
- GitHub Issues: use issues for bugs or scoped feature requests
- Email: `ethan_pier@icloud.com`

## 联系方式

如果你也在做视频知识库、RAG 或 LLM 工作流，欢迎直接联系我交流。

- GitHub Discussions： [github.com/Jia-Ethan/video-rag/discussions](https://github.com/Jia-Ethan/video-rag/discussions)
- GitHub Issues：适合反馈 bug 或明确的功能请求
- 邮箱：`ethan_pier@icloud.com`

## Project structure

```text
video-rag/
├── app/                     # Reserved for future UI work
├── docs/
│   ├── assets/
│   ├── discussions/
│   └── public-sample-output.md
├── scripts/
│   └── pipeline.py
├── data/                    # Runtime output (gitignored)
│   ├── audio/
│   ├── meta/
│   └── transcripts/
├── .github/
│   └── ISSUE_TEMPLATE/
├── CONTRIBUTING.md
├── LICENSE
└── requirements.txt
```

## License

[MIT](LICENSE)
