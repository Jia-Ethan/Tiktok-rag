# Chunk artifact spec

This document defines the current chunk-ready artifact contract for `video-rag`.

The purpose of this artifact is to provide a stable intermediate layer between raw transcript output and future indexing, retrieval, summary, or prompt-construction logic.

## File location

```text
data/chunks/<job_id>.chunks.json
```

The file name uses the same `job_id` as the transcript and metadata artifacts so downstream code can align all generated outputs from a single run.

## Top-level schema

```json
{
  "source_type": "local_video",
  "job_id": "eefd5283af40",
  "source_title": "video-rag-smoke",
  "language": "zh",
  "duration_seconds": 3.0,
  "chunking_version": "1.0",
  "chunking_strategy": "segment_grouped_char_limit_v1",
  "chunking_config": {
    "max_chars": 900,
    "overlap_segments": 1
  },
  "source_transcript_path": "/absolute/path/to/data/transcripts/<job_id>.json",
  "source_meta_path": "/absolute/path/to/data/meta/<job_id>.meta.json",
  "chunk_count": 1,
  "chunks": []
}
```

## Top-level field meanings

- `source_type`: current input source category
- `job_id`: stable run identifier shared with transcript and metadata artifacts
- `source_title`: title derived from the input file stem
- `language`: detected transcript language
- `duration_seconds`: source duration reported by transcription output
- `chunking_version`: contract version for downstream compatibility
- `chunking_strategy`: named default strategy used to build chunks
- `chunking_config`: tuning parameters used in this run
- `source_transcript_path`: transcript artifact path for traceability
- `source_meta_path`: metadata artifact path for traceability
- `chunk_count`: number of chunk objects
- `chunks`: ordered chunk list

## Chunk schema

```json
{
  "chunk_id": "eefd5283af40-chunk-000",
  "index": 0,
  "start": 0.0,
  "end": 8.4,
  "text": "Opening sentence. Next sentence continues here.",
  "char_count": 48,
  "token_estimate": 14,
  "segment_start_index": 0,
  "segment_end_index": 2,
  "segment_count": 3,
  "prev_chunk_id": null,
  "next_chunk_id": "eefd5283af40-chunk-001"
}
```

## Chunk field meanings

- `chunk_id`: stable chunk identifier scoped to the job
- `index`: zero-based chunk order
- `start` / `end`: source time range for traceability and later citation
- `text`: readable chunk text merged from transcript segments
- `char_count`: character count of the merged text
- `token_estimate`: lightweight heuristic estimate, not tokenizer-accurate
- `segment_start_index` / `segment_end_index`: inclusive transcript segment boundaries
- `segment_count`: number of transcript segments inside the chunk
- `prev_chunk_id` / `next_chunk_id`: neighboring chunk references for lightweight traversal

## Default chunking strategy

Current strategy:

`segment_grouped_char_limit_v1`

Design:

- Treat transcript segments as the atomic unit
- Group consecutive segments until a character limit is reached
- Carry over a small segment overlap between neighboring chunks

Default config:

- `max_chars = 900`
- `overlap_segments = 1`

## Why this strategy

- It preserves timestamp traceability because segment boundaries remain visible
- It is simple, stable, and easy for downstream developers to reason about
- It avoids overcommitting to semantic chunking quality before retrieval exists
- It is already useful as a retrieval-ready precursor

## Design principles

- Every chunk must map back to a clear source time range
- Every chunk must remain readable as a continuous text unit
- The output contract should be stable enough for downstream scripts to consume directly
- The artifact should not assume a specific future vector store or retrieval engine

## Known limitations

- Chunk boundaries are structural, not semantic
- `token_estimate` is heuristic, not tokenizer-accurate
- Long-video chunk quality has not been systematically evaluated
- The contract is designed as a general intermediate artifact, not a retrieval-engine-specific format

## Compatibility intent

These fields are intended to stay stable unless there is a versioned contract change:

- `job_id`
- `chunking_version`
- `chunking_strategy`
- `chunking_config`
- `source_transcript_path`
- `source_meta_path`
- `chunks[].chunk_id`
- `chunks[].index`
- `chunks[].start`
- `chunks[].end`
- `chunks[].text`
- `chunks[].segment_start_index`
- `chunks[].segment_end_index`
