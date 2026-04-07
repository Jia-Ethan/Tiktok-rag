# Public sample output

This sample shows the current public shape of `video-rag`.

The input is one downloaded local video file. The purpose of this document is to make the artifact structure easy to inspect before retrieval features exist.

## Input

- Source type: downloaded local video file
- Output mode: local video transcription pipeline

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

- This release only supports downloaded local video files.
- The current focus is clean transcript and metadata generation.
- Retrieval-related layers will come later.
