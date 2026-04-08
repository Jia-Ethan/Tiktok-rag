# Discussion seed

Suggested GitHub Discussion title:

```text
What would make video-rag useful in your workflow?
```

Suggested post body:

```md
Hi everyone,

`video-rag` currently turns downloaded local videos into timestamped transcript + metadata artifacts for downstream RAG workflows.

What works today:

- downloaded local video input
- ffmpeg audio extraction
- faster-whisper transcription
- structured transcript and metadata output

What does not exist yet:

- chunking
- retrieval
- Web UI

I would love feedback on what would make this repository useful enough to stay in your workflow.

Questions:

1. Where do your video files come from?
2. What is your typical video duration and language mix?
3. After transcription, what do you want next: retrieval, summary, knowledge organization, or prompt context construction?
4. What is the first missing step that stops this repo from being useful to you?

Direct criticism is welcome too. “This is not useful unless X exists” is valuable feedback.
```
