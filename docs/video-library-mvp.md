# Video Library MVP

这份文档说明 `video-rag` 当前这一轮的产品目标：把项目从“本地单视频处理工具”推进成“本地个人视频资料库 MVP”。

## 本轮目标

本轮重点不是增强底层 RAG，而是把下面这件事做稳：

- 我处理过很多视频
- 之后还能在本地找回来
- 能继续整理、搜索、再次进入

当前版本的产品定位是：

- 本地优先
- 单人长期使用
- 先资料库，后知识库

## 数据结构

### 现有运行层 artifact

这层仍然保留：

- `transcripts/*.json`
- `chunks/*.chunks.json`
- `meta/*.meta.json`
- `preview/*.md`
- `text/*.txt`
- `manifests/*.manifest.json`

它们代表“一次处理运行”的机器产物，不改变旧语义。

### 新增产品层记录

新增：

```text
data/library/<video_id>.video.json
```

默认规则：

- `video_id == job_id`
- 一次处理结果，对应一条视频资料记录

最小字段：

```json
{
  "video_id": "a24eb79d064c",
  "job_id": "a24eb79d064c",
  "title": "sample",
  "display_title": "sample",
  "created_at": "2026-04-08T10:19:04.443465+08:00",
  "updated_at": "2026-04-08T10:19:04.443465+08:00",
  "duration_seconds": 1.984,
  "language": "en",
  "status": "completed",
  "summary": "short local summary preview text",
  "tags": [],
  "starred": false,
  "notes": "",
  "source_file_path": "/absolute/path/to/source.mp4",
  "artifact_paths": {},
  "saved_exports": []
}
```

字段含义：

- `title`
  原始处理标题，来自输入文件名，不被手动重命名覆盖
- `display_title`
  给用户看的显示标题，可编辑
- `summary`
  本轮的结构化摘要预览，不是大模型摘要
- `tags / starred / notes`
  本轮的最小整理信息
- `saved_exports`
  当前视频历史保存结果的索引

## 页面变化

## 个人视频库

首页现在不再只是“历史纪录”。

它会展示：

- 标题 / 显示标题
- 处理时间
- 时长
- 语言
- 状态
- 摘要预览
- 标签
- 收藏状态

并支持：

- 标题关键词筛选
- 语言筛选
- 收藏状态筛选
- 最近处理 / 标题排序
- 跨视频关键词搜索

## 视频详情页

详情页保留：

- 当前视频搜索
- grounded QA
- 保存搜索结果 / 问答结果 / 单视频摘要

详情页新增：

- 视频摘要卡
- 关键信息区
- 我的备注区
- 收藏 / 显示标题 / 标签整理区
- 本地文件入口区
- 历史保存结果区

## 不做什么

本轮明确不做：

- URL 输入
- 多用户
- 线上同步
- 向量数据库
- 跨视频 grounded QA
- 自动标签优化
- semantic chunking 重做

## 如何衔接下一轮 multi-video knowledge layer

这轮把“资料层”做稳后，下一轮才适合进入“知识层”。

最合理的衔接顺序是：

1. 在现有视频库记录和 chunk artifact 上补更稳的跨视频 retrieval-ready layer
2. 先用本地 embedding / hybrid retrieval 验证多视频召回
3. 再决定是否进入更像“个人知识助手”的交互层

换句话说：

- 这轮解决“怎么沉淀、整理、找回来”
- 下一轮再解决“怎么跨视频理解、组合、回答”
