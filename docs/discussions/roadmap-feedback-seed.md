# Roadmap / feedback seed

Suggested GitHub Discussion title:

```text
Roadmap feedback: what should come right after local short-video transcription?
```

Suggested post body:

```md
Hi everyone,

`Tiktok-rag` is currently a local-video-first MVP that turns short videos into timestamped transcript + metadata artifacts for downstream LLM workflows.

What works today:

- local video file input
- ffmpeg audio extraction
- faster-whisper transcription
- structured transcript and metadata output

What is not publicly reliable yet:

- Douyin/TikTok URL ingestion
- chunking
- retrieval
- Web UI

I would love feedback on what should come next.

Questions:

1. Would a local-file-first short-video RAG tool already be useful for you?
2. After transcription, what matters more: chunking, retrieval, or better ingestion boundaries?
3. If you work with short videos, what is the actual workflow you want to enable for your LLM?
4. Should this stay developer-first, or become more productized over time?

Direct criticism is welcome too. “This is not useful unless X exists” is valuable feedback.
```
