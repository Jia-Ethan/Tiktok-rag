# Tiktok-rag 中文说明

`Tiktok-rag` 是一个面向开发者的 short-video RAG MVP。

它当前专注做一件事：把本地短视频稳定地转成带时间戳的结构化文本结果，作为后续 chunking、检索、摘要和 LLM 上下文构建的起点。

## 当前稳定能力

- 输入本地视频文件：`.mp4` / `.mov` / `.mkv`
- 使用 `ffmpeg` 抽取 16kHz 单声道音频
- 使用 `faster-whisper` 生成带时间戳 transcript JSON
- 输出 metadata JSON，方便后续继续处理

## 当前边界

- 公开可用能力目前只支持本地视频文件
- Douyin/TikTok URL 输入目前只是实验性占位，不是可靠公开功能
- 这一版还没有 chunking、向量库、检索界面和 Web UI

## 项目目标

目标不是先做“最全功能”，而是先把短视频进入 LLM 工作流的第一步做稳定：

`short video -> transcript -> structured artifacts -> future retrieval`

## 英文主文档

公开 GitHub 首页说明请看：

- [README.md](../README.md)
