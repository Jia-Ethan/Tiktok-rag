# 公开样例输出

以下为本地 mp4 链路验证的实际输出（2026-04-07），输入为一段微信视频（189 秒）。

> 注意：此样例音频内容为英文歌曲，Whisper base 模型仍输出了时间戳准确的转写。中文内容的转写效果通常更好。

---

## 输入

- **来源类型：** 本地 mp4 文件
- **文件：** `微信视频2026-03-30_111151_513.mp4`
- **时长：** 189.5 秒（约 3 分钟）
- **大小：** 34 MB

---

## Transcript JSON（`data/transcripts/<hash>.json`）

```json
{
  "model": "base",
  "language": "zh",
  "duration_seconds": 189.47,
  "segments": [
    {
      "start": 0.0,
      "end": 2.4,
      "text": " walking along the road,"
    },
    {
      "start": 3.0,
      "end": 5.4,
      "text": " brained back speed memories,"
    },
    {
      "start": 6.8,
      "end": 10.0,
      "text": " I can't forget how we used to keep,"
    },
    {
      "start": 10.5,
      "end": 12.9,
      "text": " I can't forget your tenderness,"
    },
    {
      "start": 14.3,
      "end": 16.3,
      "text": " loving you more and more,"
    }
    // ... 共 48 段
  ]
}
```

---

## Metadata JSON（`data/meta/<hash>.meta.json`）

```json
{
  "source_type": "local_mp4",
  "platform": "local",
  "input_path": "your/video.mp4",
  "input_size_bytes": 34561319,
  "video_id": null,
  "title": "微信视频2026-03-30_111151_513",
  "caption": null,
  "audio_path": "data/audio/6c2105b2808a.wav",
  "transcript_path": "data/transcripts/6c2105b2808a.json",
  "transcript_segments": 48,
  "transcript_duration_seconds": 189.47,
  "whisper_model": "base",
  "created_at": "2026-04-07T22:23:35+08:00"
}
```

---

## 目录结构（运行时）

```
data/
├── audio/           ← 16kHz WAV，5.8MB（此样例）
│   └── 6c2105b2808a.wav
├── transcripts/     ← 转写 JSON，41KB（此样例）
│   └── 6c2105b2808a.json
└── meta/           ← 元数据 JSON
    └── 6c2105b2808a.meta.json
```

---

## 质量说明

- **时间戳精度：** 0.01 秒（Whisper 词级时间戳）
- **语言检测：** 模型自动判断（此样例判断为 zh，输出为英文歌曲内容）
- **转写速度：** MacBook Air M2，CPU 推理，约 45 秒处理 189 秒音频
- **适用内容：** 普通话/英语清晰语音效果最佳，音乐/多人对话/强方言待测
