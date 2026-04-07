# MVP Step 1 Report

Historical note for the first public MVP validation on 2026-04-07.

## What was validated

- Local video file input works end to end.
- `ffmpeg` audio extraction works with the current pipeline.
- `faster-whisper` generates timestamped transcript JSON.
- Metadata JSON is written in a stable structure for downstream processing.

## What was intentionally deferred

- Reliable Douyin/TikTok URL ingestion
- Chunking
- Vector store integration
- Retrieval UX

## Why this still mattered

The first milestone was never “full short-video RAG.” It was “make the first reliable step public and reproducible.” That goal was reached with the local-video-first pipeline.
