# Discussion seed

Suggested GitHub Discussion title:

```text
What would make video-rag useful in your workflow?
```

Suggested post body:

```md
Hi everyone,

`video-rag` currently turns downloaded local videos into transcript, metadata, and chunk-ready artifacts for downstream RAG workflows.

What works today:

- downloaded local video input
- ffmpeg audio extraction
- faster-whisper transcription
- structured transcript, metadata, and chunk-ready output

What does not exist yet:

- retrieval
- Web UI

I would love feedback on what would make this repository useful enough to stay in your workflow.

Questions:

1. Where do your video files come from?
2. What is your typical video duration and language mix?
3. Is the current chunk-ready artifact already enough for your downstream integration, or what is still missing?
4. What is the first missing step that stops this repo from being useful to you?

Direct criticism is welcome too. “This is not useful unless X exists” is valuable feedback.
```
