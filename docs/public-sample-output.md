# Developer doc: public sample output

This sample shows what `video-rag` produces today and why those artifacts matter.

If you are just trying the tool for the first time, start with [beginner-quickstart.md](beginner-quickstart.md) and open the generated `preview.md` or `text.txt` first.

The current release still does **not** implement retrieval. What it does provide now is a reliable path from downloaded video input to transcript, metadata, chunk-ready artifacts, readable text, and manifest outputs.

## Input

- Source type: downloaded local video file
- Processing mode: single-video local ingestion, transcription, and chunk artifact generation

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
- the raw transcription layer before downstream grouping

### Metadata artifact

Path pattern:

```text
data/meta/<job_id>.meta.json
```

Example shape:

```json
{
  "job_id": "6c2105b2808a",
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
  "chunk_path": "/absolute/path/to/data/chunks/<job_id>.chunks.json",
  "chunk_count": 4,
  "chunking_strategy": "segment_grouped_char_limit_v1",
  "chunking_version": "1.0",
  "created_at": "2026-04-07T22:23:35+08:00"
}
```

What this gives you:

- traceability back to the original input file
- links between source video, extracted audio, transcript output, and chunk output
- processing context for downstream systems

### Readable text artifact

Path pattern:

```text
data/text/<job_id>.txt
```

What this gives you:

- the simplest plain-text output for ordinary reading
- a copy-friendly version for note-taking or pasting into other tools
- a result that does not require opening JSON first

### Preview artifact

Path pattern:

```text
data/preview/<job_id>.md
```

What this gives you:

- a beginner-friendly result page
- title, time, file guide, and chunk preview in one place
- the best first file to open after a run

### Chunk artifact

Path pattern:

```text
data/chunks/<job_id>.chunks.json
```

Example shape:

```json
{
  "source_type": "local_video",
  "job_id": "6c2105b2808a",
  "source_title": "sample-video",
  "language": "zh",
  "duration_seconds": 189.47,
  "chunking_version": "1.0",
  "chunking_strategy": "segment_grouped_char_limit_v1",
  "chunking_config": {
    "max_chars": 900,
    "overlap_segments": 1
  },
  "source_transcript_path": "/absolute/path/to/data/transcripts/<job_id>.json",
  "source_meta_path": "/absolute/path/to/data/meta/<job_id>.meta.json",
  "chunk_count": 2,
  "chunks": [
    {
      "chunk_id": "6c2105b2808a-chunk-000",
      "index": 0,
      "start": 0.0,
      "end": 10.0,
      "text": "walking along the road, brained back speed memories, I can't forget how we used to keep,",
      "char_count": 94,
      "token_estimate": 24,
      "segment_start_index": 0,
      "segment_end_index": 2,
      "segment_count": 3,
      "prev_chunk_id": null,
      "next_chunk_id": "6c2105b2808a-chunk-001"
    }
  ]
}
```

What this gives you:

- a stable intermediate unit that downstream scripts can consume directly
- a readable chunk text field instead of forcing every user to rebuild grouping logic from raw transcript segments
- explicit time range and segment boundaries for citation and traceability
- neighbor references for lightweight traversal or prompt assembly
- the first practical integration point if you want to add embeddings, indexing, retrieval, or summary logic on top of `video-rag`

### Manifest artifact

Path pattern:

```text
data/manifests/<job_id>.manifest.json
```

Example shape:

```json
{
  "job_id": "6c2105b2808a",
  "status": "completed",
  "source_type": "local_video",
  "source_title": "sample-video",
  "language_requested": "auto",
  "language_detected": "zh",
  "duration_seconds": 189.47,
  "model": "base",
  "created_at": "2026-04-08T09:33:29+08:00",
  "counts": {
    "segments": 48,
    "chunks": 4
  },
  "summary": {
    "start_here": "/absolute/path/to/data/preview/<job_id>.md",
    "best_plain_text": "/absolute/path/to/data/text/<job_id>.txt"
  },
  "artifact_paths": {
    "text_txt": "/absolute/path/to/data/text/<job_id>.txt",
    "preview_markdown": "/absolute/path/to/data/preview/<job_id>.md",
    "transcript_json": "/absolute/path/to/data/transcripts/<job_id>.json",
    "chunks_json": "/absolute/path/to/data/chunks/<job_id>.chunks.json",
    "metadata_json": "/absolute/path/to/data/meta/<job_id>.meta.json",
    "manifest_json": "/absolute/path/to/data/manifests/<job_id>.manifest.json"
  }
}
```

What this gives you:

- one machine-friendly summary of the whole run
- a direct integration point for local UIs and automation
- a reliable way to discover which output file a normal user should open first

## Runtime directory layout

```text
data/
├── audio/
│   └── <job_id>.wav
├── chunks/
│   └── <job_id>.chunks.json
├── manifests/
│   └── <job_id>.manifest.json
├── meta/
│   └── <job_id>.meta.json
├── preview/
│   └── <job_id>.md
├── text/
│   └── <job_id>.txt
└── transcripts/
    └── <job_id>.json
```

## Why these artifacts matter

- Transcript turns video content into inspectable text
- Metadata keeps source relationships and processing context intact
- Readable text and preview outputs make the pipeline usable for non-technical users
- Chunks turn raw transcript output into retrieval-ready precursors without locking the repo into a specific vector stack
- Together they provide a cleaner starting point for indexing, retrieval, summary generation, and prompt context construction

## Reliability notes

- This release only supports downloaded local video files
- The chunking strategy is structural and conservative, not semantic
- The current output format is stable enough for downstream experimentation
- Systematic benchmarking for long videos, multilingual audio, noisy inputs, and multi-speaker scenarios is still pending

For the current contract and the fields we intend to keep stable, see [chunk-artifact-spec.md](chunk-artifact-spec.md).
