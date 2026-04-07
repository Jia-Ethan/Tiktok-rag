# Roadmap / feedback seed

Suggested GitHub Discussion title:

```text
Roadmap feedback: what should come right after local video transcription?
```

Suggested post body:

```md
Hi everyone,

`video-rag` currently turns downloaded local videos into timestamped transcript + metadata artifacts for downstream LLM workflows.

What works today:

- downloaded local video input
- ffmpeg audio extraction
- faster-whisper transcription
- structured transcript and metadata output

What does not exist yet:

- chunking
- retrieval
- Web UI

I would love feedback on what should come next.

Questions:

1. Would a downloaded-video-first workflow already be useful for you?
2. After transcription, what matters more: chunking, retrieval, or artifact structure improvements?
3. If you work with video knowledge, what workflow are you trying to enable for your LLM?
4. Should this stay developer-first, or become more productized over time?

Direct criticism is welcome too. “This is not useful unless X exists” is valuable feedback.
```
