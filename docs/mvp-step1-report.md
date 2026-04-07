# MVP Step 1 Report — 抖音短视频知识库

**日期：** 2026-04-07
**阶段：** 输入链路验证 + 项目骨架初始化

---

## 一、项目骨架

```
short-video-brain-mvp/
├── app/                  # Web UI（未来阶段）
├── scripts/
│   └── pipeline.py       # 核心管线
├── data/
│   ├── raw/              # 原始视频（抖音路线）
│   ├── audio/            # 16kHz WAV
│   ├── transcripts/       # 带时间戳 JSON
│   └── meta/             # 标准化 metadata JSON
├── docs/
│   └── mvp-step1-report.md
├── README.md
└── requirements.txt       # 无（无 pip 依赖文件，仅本地安装）
```

---

## 二、已成功验证的部分

### ✅ 完整链路跑通（本地 mp4）

```
mp4 (34MB, 189s)
  → ffmpeg 音频抽出 (.wav, 16kHz, mono)
  → faster-whisper base 模型转写
  → transcript JSON (48 segments)
  → metadata JSON
```

**实测结果：**
- 输入：`your/video.mp4`
- 音频：`data/audio/6c2105b2808a.wav`
- 转写：`data/transcripts/6c2105b2808a.json`（48 段，189.5 秒）
- 元数据：`data/meta/6c2105b2808a.meta.json`
- 耗时：约 45 秒（CPU 推理，MacBook Air M2）

**Transcript 示例（前 5 段）：**
```
[0.0s - 2.4s] walking along the road,
[3.0s - 5.4s] brained back speed memories,
[6.8s - 10.0s] I can't forget how we used to keep,
[10.5s - 12.9s] I can't forget your tenderness,
[14.3s - 16.3s] loving you more and more,
```
> 注：实测内容为英文歌曲，说明 Whisper `base` 模型对非普通话内容也能正常输出时间戳。语言检测显示 100% 中文但输出英文（模型判断了语言，但实际音频内容不同）。

**Metadata 片段：**
```json
{
  "source_type": "local_mp4",
  "platform": "local",
  "input_path": "your/video.mp4",
  "audio_path": ".../data/audio/6c2105b2808a.wav",
  "transcript_path": ".../data/transcripts/6c2105b2808a.json",
  "transcript_segments": 48,
  "transcript_duration_seconds": 189.47,
  "whisper_model": "base",
  "created_at": "2026-04-07T22:23:35+08:00"
}
```

---

## 三、卡点与原因

### ⚠️ 抖音分享链接路线（未完全打通）

**原因：** `yt-dlp` 下载抖音视频需要登录 cookies。测试 `yt-dlp "https://www.douyin.com/video/7234567890123456789"` 返回错误：
```
ERROR: [Douyin] Fresh cookies (not necessarily logged in) are needed
```
这是抖音的防爬机制，非付费 API 可以解决。

**现状判断：** 不影响 MVP 验证。已建立完整本地 mp4 链路，抖音路线已写好降级逻辑（下载失败时直接报错退出，提示使用本地 mp4）。

### ⚠️ faster-whisper 安装路径

faster-whisper 需要额外安装（`pip3 install faster-whisper --target ~/PythonPackages`），不在系统 Python 标准库里。已通过 `PYTHONPATH=~/PythonPackages` 解决。

---

## 四、依赖与启动方式

| 依赖 | 状态 | 备注 |
|------|------|------|
| `ffmpeg` | ✅ 已有 | v8.0.1 |
| `yt-dlp` | ✅ 已有 | v2024.x |
| `faster-whisper` | ✅ 已安装 | v1.2.1 → `~/PythonPackages` |
| Python 3 | ✅ 已有 | 3.14.3 |

**启动方式：**
```bash
python3 scripts/pipeline.py \
  --input your/video.mp4 \
  --output-dir ./data
```

---

## 五、第二阶段建议（transcript → chunk → Chroma → search）

### 建议任务清单

1. **音视频分段（chunking）**
   - 按句子/段落将 transcript segments 合并为 chunks
   - 保留时间戳上下文（用于视频时间定位）
   - 每个 chunk 附 metadata（来源 video_id、时间范围）

2. **Chroma 向量数据库**
   - 安装：`pip3 install chromadb --target ~/PythonPackages`
   - 将 chunks 转为 embeddings（用本地 embedding 模型，如 `sentence-transformers`）
   - 建立 collection：`douyin_video_segments`

3. **语义搜索接口**
   - `query → embedding → Chroma similarity search → 返回 chunks + 来源视频`
   - 支持时间戳定位（跳转到视频对应时间点）

4. **可选：抖音账号登录（后续再接）**
   - 用 opencli 或 playwright 自动化登录抖音
   - 获取用户视频列表 → 批量下载 → 批量转写

---

## 六、已知限制

- [x] 本地 mp4 链路 ✅
- [ ] 抖音分享链接（需登录 cookies）
- [ ] OCR 模组（未实现，预留接口）
- [ ] 登入/账号系统（无计划）
- [ ] 批量同步（无计划）
