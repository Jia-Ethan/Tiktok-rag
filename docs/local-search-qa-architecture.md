# Local search + QA architecture

这份文档只说明这一轮新增的本地单视频搜索与 grounded QA 闭环，不重复介绍基础转写流程。

## 页面结构

当前 Gradio UI 分成两个工作区：

1. `处理新视频`
   - 负责选择本地视频并运行现有 pipeline
   - 继续输出 transcript / chunk / preview / manifest 等 artifact
2. `历史纪录 / 当前视频`
   - 读取 `data/manifests/*.manifest.json`
   - 展示历史纪录 / 视频库
   - 进入单视频详情页
   - 执行当前视频搜索、当前视频 grounded QA、匯出

## 资料流

### 处理阶段

`app/gradio_app.py`
→ 调用 `scripts/pipeline.py::run_pipeline()`
→ 生成：

- `audio/*.wav`
- `transcripts/*.json`
- `chunks/*.chunks.json`
- `meta/*.meta.json`
- `preview/*.md`
- `text/*.txt`
- `manifests/*.manifest.json`

### 首页历史纪录

`历史纪录 / 视频库` 不另建数据库，直接扫描：

```text
data/manifests/*.manifest.json
```

manifest 是唯一主资料源。

如果 manifest 某些字段不够显示，只做最小兼容补读：

- 优先从 `artifact_paths.metadata_json` 读取旧 `meta`
- 不另起第二套主索引

## 搜索流程

搜索只针对**当前选中的一个视频**。

流程：

1. 读取当前视频的 `.chunks.json`
2. 对每个 chunk 文本做本地关键词匹配
3. 返回命中结果列表
4. 用户点击结果后，详情页 chunk 浏览区同步定位到该 chunk

当前评分策略是轻量、可解释的：

- 原查询整句命中优先
- 非 CJK 文本使用小写 token overlap + phrase match
- CJK 文本使用子串与 2-gram overlap

这一层的目标是：

- 先做可用、可核对、可定位
- 不承诺 semantic retrieval

## QA 流程

QA 只允许基于**当前单视频**内容回答。

流程：

1. 用户在当前视频详情页输入问题
2. 系统先对当前视频 chunks 做关键词检索
3. 取 top-k 相关 chunks 作为 evidence
4. 组装 grounded prompt
5. 调用 OpenAI 兼容 API
6. 解析结构化 JSON 输出
7. 展示答案与引用
8. 用户点击引用后，chunk 浏览区同步定位到对应时间段

## QA 输出 contract

当前要求模型返回 JSON，核心字段为：

```json
{
  "answer": "string",
  "insufficient_evidence": true,
  "citations": [
    {
      "chunk_id": "string",
      "chunk_index": 0,
      "start": 0.0,
      "end": 8.4,
      "support_summary": "string"
    }
  ]
}
```

若依据不足：

- `insufficient_evidence` 必须为 `true`
- 系统会明确提示“当前视频内容中没有足够依据”
- 不允许硬答

## 匯出流程

本轮匯出统一写到：

```text
data/exports/<job_id>/
```

当前支持：

- `search-<timestamp>.md`
- `qa-<timestamp>.md`
- `summary-<timestamp>.md`

这三类匯出都以“可直接打开、可直接复用”为目标，不做复杂格式。

## 后续扩展口

这一轮刻意保持克制。后面如果要继续扩展，最自然的口子是：

1. 把当前关键词检索替换成 hybrid retrieval
2. 在不破坏现有 chunk contract 的前提下补本地 embedding
3. 从单视频 QA 扩到多视频 retrieval-ready loop
4. 再考虑更强的结果浏览器与多视频组织层
