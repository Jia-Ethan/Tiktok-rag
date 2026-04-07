# Public sample output

This is a real output sample from the current local-video pipeline.

The input was a local video file around 189 seconds long. The goal of this sample is not to prove perfect transcription quality for every case. It is to show the exact artifact shape this project produces today.

## Input

- Source type: local video file
- Duration: 189.5 seconds
- Output mode: local-first transcription pipeline

## Transcript artifact

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

## Metadata artifact

Path pattern:

```text
data/meta/<job_id>.meta.json
```

Example shape:

```json
{
  "source_type": "local_mp4",
  "platform": "local",
  "input_path": "/absolute/path/to/video.mp4",
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

## Notes

- The current release optimizes for a clean, inspectable pipeline rather than end-user polish.
- Local files are the only stable public input mode right now.
- Douyin/TikTok URL ingestion is not part of the guaranteed workflow in this release.
