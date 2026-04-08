# video-rag

**Turn a local video file into readable text, chunk previews, and downloadable artifacts on your own machine.**

把一个已经下载到本地的视频，处理成普通用户可直接阅读的文本结果，以及开发者后续可继续接入的结构化 artifact。

当前版本最适合做的事情不是“完整 Video RAG”，而是先把视频内容稳定地转成：

- 一份普通用户可以直接打开阅读的结果页
- 一份可以复制、整理、做笔记的纯文本
- 一组供开发者后续继续做 chunking / indexing / retrieval 的结构化文件

![video-rag UI](docs/assets/ui-demo.png)

## 它现在能帮你做什么

你选一个本地视频文件，点开始处理，然后会得到：

- 可直接阅读的 transcript 文本
- 带时间信息和 chunk 预览的结果页
- 可下载的 `txt / md / json` 文件
- 一份把所有输出文件串起来的 manifest

你不需要先打开 JSON，第一次使用时直接看 `preview.md` 或 `text.txt` 就够了。

## 适合谁

- 想把本地视频先转成可读文本的人
- 想整理课程、访谈、分享、短视频内容的人
- 想先跑通“视频 -> 文本结果”这一步，再决定后面要不要接检索、摘要或知识整理的人
- 本地优先，不想先搭建数据库、向量库或网页服务的个人用户和独立开发者

## 不适合谁

- 想直接贴 URL 就完成全流程的人
- 期待项目现在已经自带问答、检索或知识库搜索的人
- 需要在线部署、团队协作、多视频复杂管理的人
- 需要高质量 semantic chunking 或系统 benchmark 结果的人

## 小白第一次使用路径

1. 准备一个已经下载到本地的视频文件
2. 安装 `ffmpeg`
3. 创建虚拟环境并安装依赖
4. 运行本地 UI：`python3 app/gradio_app.py`
5. 在浏览器里选择视频文件，点“开始处理”
6. 处理完成后先看 `preview.md`，再看 `text.txt`

更详细的普通用户说明见：

- [docs/beginner-quickstart.md](docs/beginner-quickstart.md)

## 我处理完视频后会得到什么

默认输出目录在 `data/` 下。

### 最适合普通用户先打开的文件

- `data/preview/<job_id>.md`
  这是最适合第一次打开看的文件。它会告诉你这次处理的标题、语言、时长、chunk 预览，以及每个输出文件该怎么用。
- `data/text/<job_id>.txt`
  这是最适合直接阅读、复制、贴进笔记软件或发给别人的纯文本版本。

### 其他输出文件

- `data/transcripts/<job_id>.json`
  原始时间戳 transcript，适合开发者或后续脚本处理。
- `data/chunks/<job_id>.chunks.json`
  chunk-ready 中间层 artifact，适合后续做 indexing、retrieval 或 summary pipeline。
- `data/meta/<job_id>.meta.json`
  处理元数据，负责把输入视频和输出文件关系串起来。
- `data/manifests/<job_id>.manifest.json`
  一次运行的摘要文件，适合 UI、自动化脚本或外部工具直接读取。
- `data/audio/<job_id>.wav`
  从原视频抽出的标准化音频。

## 快速开始

### 1. 准备环境

- Python 3.9+
- `ffmpeg`

安装 `ffmpeg`：

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg
```

### 2. 安装依赖

```bash
git clone https://github.com/Jia-Ethan/video-rag.git
cd video-rag
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
```

### 3. 启动本地 UI

```bash
python3 app/gradio_app.py
```

启动后打开终端里显示的本地地址，通常是：

```text
http://127.0.0.1:7860
```

如果你的环境里 `127.0.0.1` 访问有问题，可以这样启动：

```bash
VIDEO_RAG_HOST=0.0.0.0 VIDEO_RAG_PORT=7860 python3 app/gradio_app.py
```

### 4. 如果你更习惯命令行

```bash
python3 scripts/pipeline.py \
  --input /path/to/local-video.mp4 \
  --output-dir ./data \
  --language auto
```

## 语言支持

- 默认使用 `auto` 自动识别语言
- 你也可以手动指定语言，例如 `zh`、`en`、`ja`
- 当前公开样例和人工检查主要还是围绕中文语音场景
- 英文、混合语言、噪音环境、多说话人场景理论上可通过 `faster-whisper` 处理，但还没有系统 benchmark

如果自动识别不稳定，优先试：

- 手动指定语言
- 换更短的视频片段
- 先用 `base` 或 `small` 模型验证流程

## 这个项目现在到底是什么

它现在是一个本地优先的视频 ingestion / transcription 工具，加上一层普通用户可读的本地结果页。

它还不是：

- 完整 Video RAG 产品
- 自带 retrieval / 向量库 / Web 部署的平台
- URL 下载器

它下一步最合理的发展方向是：

- 在当前 chunk-ready artifact 之上做最小 retrieval-ready loop

## 输出为什么有价值

- 普通用户不需要读 JSON，也能直接看到可读文本和结果页
- 开发者不需要从 transcript 重新手工整理 chunk
- 同一轮处理同时产出“可读层”和“结构层”
- 时间戳和 chunk 边界还在，后面继续做引用、检索或 prompt construction 不需要返工

## 已知限制

- 只支持本地视频文件，不支持 URL
- 还没有 retrieval、向量库、网页部署和多视频管理
- 当前 chunking 是结构型、保守型策略，不是 semantic chunking
- 长视频、多语言、强噪音、多说话人场景还没有系统 benchmark

## 普通用户文档

- [docs/beginner-quickstart.md](docs/beginner-quickstart.md)

## Developer docs

- [docs/public-sample-output.md](docs/public-sample-output.md)
- [docs/chunk-artifact-spec.md](docs/chunk-artifact-spec.md)
- [docs/feedback-guide.md](docs/feedback-guide.md)

## 项目结构

```text
video-rag/
├── app/
│   └── gradio_app.py
├── docs/
│   ├── assets/
│   ├── beginner-quickstart.md
│   ├── chunk-artifact-spec.md
│   ├── feedback-guide.md
│   └── public-sample-output.md
├── scripts/
│   └── pipeline.py
├── data/
│   ├── audio/
│   ├── chunks/
│   ├── manifests/
│   ├── meta/
│   ├── preview/
│   ├── text/
│   └── transcripts/
└── requirements.txt
```

## 反馈

- 新手体验反馈：GitHub Issues 里的 beginner / UX 模板
- 路线和工作流反馈：[GitHub Discussions](https://github.com/Jia-Ethan/video-rag/discussions)
- 直接联系：`ethan_pier@icloud.com`

## License

[MIT](LICENSE)
