# Public sample output

This sample shows what `video-rag` produces today and why those artifacts matter.

The current release does **not** implement retrieval yet. Its job is to produce stable, inspectable text assets that later retrieval layers can build on.

## Input

- Source type: downloaded local video file
- Processing mode: single-video local ingestion and transcription

## Artifact schema

### Transcript artifact

Path pattern:

```text
data/transcripts/<job_id>.json
```

Example shape:

```json
{
  "model": "base",
  "language": "zh",
  "duration_seconds": 189.47,
  "segments": [
    {
      "start": 0.0,
      "end": 2.4,
      "text": "walking along the road,"
    },
    {
      "start": 3.0,
      "end": 5.4,
      "text": "brained back speed memories,"
    },
    {
      "start": 6.8,
      "end": 10.0,
      "text": "I can't forget how we used to keep,"
    }
  ]
}
```

What this gives you:

- readable text extracted from the video
- segment-level timestamps for traceability
- a structure that can later be chunked or indexed

### Metadata artifact

Path pattern:

```text
data/meta/<job_id>.meta.json
```

Example shape:

```json
{
  "source_type": "local_video",
  "platform": "local",
  "input_path": "/absolute/path/to/downloaded-video.mp4",
  "input_size_bytes": 34561319,
  "video_id": null,
  "title": "sample-video",
  "caption": null,
  "audio_path": "/absolute/path/to/data/audio/<job_id>.wav",
  "transcript_path": "/absolute/path/to/data/transcripts/<job_id>.json",
  "transcript_segments": 48,
  "transcript_duration_seconds": 189.47,
  "whisper_model": "base",
  "created_at": "2026-04-07T22:23:35+08:00"
}
```

What this gives you:

- traceability back to the original input file
- links between source video, extracted audio, and transcript output
- processing context for downstream systems

## Runtime directory layout

```text
data/
├── audio/
│   └── <job_id>.wav
├── meta/
│   └── <job_id>.meta.json
└── transcripts/
    └── <job_id>.json
```

## Why these artifacts matter

- They turn video content into text you can inspect, quote, and review
- Timestamps make later source alignment and jump-back review possible
- Metadata prevents transcript files from becoming detached from their source context
- Together they form a cleaner starting point for chunking, indexing, retrieval, summary generation, and prompt context construction

## Reliability notes

- This release only supports downloaded local video files
- The current output format is stable enough for downstream experimentation
- Systematic benchmarking for long videos, multilingual audio, noisy inputs, and multi-speaker scenarios is still pending
