# video-rag

**Build a local personal video library that you can process, organize, search, revisit, and reuse on your own machine.**

`video-rag` 现在已经不只是“本地单视频转文字工具”。

当前版本的产品定位是：

- 本地个人视频资料库 MVP
- 先把视频资产沉淀下来、整理起来、能再次进入
- 再为后续 multi-video knowledge loop 打基础

你现在可以在同一个本地 UI 里完成这条闭环：

- 处理多个本地视频
- 在“个人视频库”里找回它们
- 按标题、语言、收藏状态筛选
- 对当前筛选范围做跨视频关键词搜索
- 进入某个视频详情页继续做当前视频搜索和 grounded QA
- 收藏、改显示标题、加标签、写备注
- 把搜索结果、问答结果、单视频摘要保存到本地，并在详情页再次打开

它仍然**不是**完整 Video RAG 平台。当前不支持 URL、线上部署、多用户、向量数据库、跨视频 grounded QA 或 semantic retrieval。

![video-rag UI](docs/assets/ui-demo.png)

## 它现在能帮你做什么

如果你已经处理过很多本地视频，`video-rag` 现在可以帮你把这些视频变成一个可持续使用的个人资料库：

- 不需要再记 `job_id`
- 不需要先翻 JSON 才能找到内容
- 不需要每次都从头处理、从头定位

你可以先在视频库页找到目标视频，再进入详情页继续：

- 看摘要预览
- 看本地文件入口
- 搜索当前视频内容
- 对当前视频提问
- 查看引用时间段
- 保存结果并留在这条视频资料上

## 适合谁

- 本地优先、单人长期使用的人
- 想把处理过的课程、访谈、分享、素材沉淀成个人资料库的人
- 想先把“资料管理层”做稳，再考虑更复杂知识库的人
- 不想一开始就搭数据库、向量库、线上服务的个人用户与独立开发者

## 不适合谁

- 想直接贴 URL 跑全流程的人
- 需要线上同步、多用户协作的人
- 期待当前版本已经是完整多视频知识库或完整 Video RAG 平台的人
- 想先做 semantic retrieval、vector DB、大规模 benchmark 的人

## 第一次使用路径

1. 准备一个已经下载到本地的视频文件
2. 安装 `ffmpeg`
3. 创建虚拟环境并安装依赖
4. 运行本地 UI：`python3 app/gradio_app.py`
5. 处理一个或多个本地视频
6. 回到“个人视频库”页筛选、搜索、整理
7. 进入某个视频详情页继续做当前视频搜索和 grounded QA

普通用户说明见：

- [docs/beginner-quickstart.md](docs/beginner-quickstart.md)

## 处理完后会得到什么

### 最适合普通用户先看的

- `data/preview/<job_id>.md`
  第一次整体查看这次处理结果。
- `data/text/<job_id>.txt`
  最适合直接阅读、复制、贴到笔记软件。
- `data/library/<video_id>.video.json`
  这是产品层的资料记录，会保存显示标题、标签、收藏、备注、保存结果历史等信息。

### 最适合在 UI 里继续做的

- 在个人视频库中筛选和找回视频
- 跨视频做基础关键词搜索
- 在详情页继续搜索当前视频
- 在详情页做 grounded QA
- 保存搜索结果、问答结果、单视频摘要

### 结构化输出文件

- `data/transcripts/<job_id>.json`
  原始时间戳 transcript。
- `data/chunks/<job_id>.chunks.json`
  当前视频搜索、grounded QA 和后续检索层的基础 artifact。
- `data/meta/<job_id>.meta.json`
  一次处理运行的元数据。
- `data/manifests/<job_id>.manifest.json`
  一次处理运行的机器摘要。
- `data/library/<video_id>.video.json`
  面向长期使用的产品层视频记录。

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

默认地址通常是：

```text
http://127.0.0.1:7860
```

如果你更习惯命令行，也可以继续用：

```bash
python3 scripts/pipeline.py \
  --input /path/to/local-video.mp4 \
  --output-dir ./data \
  --language auto
```

## 产品边界

它现在是：

- 本地个人视频资料库 MVP
- 本地单视频搜索与 grounded QA 闭环
- 本地保存整理信息和保存结果历史的资料层

它还不是：

- 完整 Video RAG 平台
- 多视频 semantic retrieval 系统
- 向量数据库方案
- 跨视频 grounded QA
- URL 下载器
- 线上部署产品

## 本地搜索与问答怎么工作

- “跨视频搜索”只做基础关键词搜索，不做 embedding
- “当前视频搜索”只搜当前视频的 `chunks.json`
- grounded QA 只基于当前选中视频的 chunks 回答
- 答案必须带引用；引用至少对应 chunk 编号和时间段
- 如果当前视频没有足够依据，系统会明确拒答，不会硬答

### QA 配置

当前 grounded QA 使用 **OpenAI 兼容 API**。你可以用环境变量预设，也可以在 UI 的 QA 设置里临时填写：

- `VIDEO_RAG_QA_BASE_URL`
- `VIDEO_RAG_QA_MODEL`
- `VIDEO_RAG_QA_API_KEY`

API key 只保存在当前 UI 会话里，不写入磁盘。

## 已知限制

- 只支持本地视频文件，不支持 URL
- 跨视频搜索仍然是关键词匹配，不是 semantic retrieval
- grounded QA 仍然只针对当前单视频，不支持跨视频问答
- 资料记录默认按“一次处理一条资料”建模，不做同源视频合并
- 长视频、多语言、强噪音、多说话人场景还没有系统 benchmark

## 文档

### 普通用户文档

- [docs/beginner-quickstart.md](docs/beginner-quickstart.md)

### 产品 / 架构文档

- [docs/video-library-mvp.md](docs/video-library-mvp.md)
- [docs/video-library-mvp-smoke-test.md](docs/video-library-mvp-smoke-test.md)
- [docs/local-search-qa-architecture.md](docs/local-search-qa-architecture.md)

### Developer docs

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
│   ├── local-search-qa-architecture.md
│   ├── video-library-mvp.md
│   ├── video-library-mvp-smoke-test.md
│   └── public-sample-output.md
├── scripts/
│   └── pipeline.py
├── data/
│   ├── audio/
│   ├── chunks/
│   ├── exports/
│   ├── library/
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
