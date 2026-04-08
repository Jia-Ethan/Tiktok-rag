#!/usr/bin/env python3
"""
video-rag pipeline.

This release supports downloaded local video files only.
It produces transcript, metadata, chunk-ready artifacts, and beginner-friendly
text / preview outputs.

Quickstart:
  python3 scripts/pipeline.py --input /path/to/downloaded-video.mp4 --output-dir ./data
"""
import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional, Union


CST = timezone(timedelta(hours=8))

DEFAULT_WHISPER_MODEL = "base"
DEFAULT_COMPUTE_TYPE = "auto"
DEFAULT_LANGUAGE = "auto"
FFMPEG_BIN = "ffmpeg"

DEFAULT_CHUNK_MAX_CHARS = 900
DEFAULT_CHUNK_OVERLAP_SEGMENTS = 1
CHUNKING_VERSION = "1.0"
CHUNKING_STRATEGY = "segment_grouped_char_limit_v1"

SUPPORTED_MODELS = ["tiny", "base", "small", "medium", "large-v3"]
COMMON_LANGUAGE_CHOICES = ["auto", "zh", "en", "ja", "ko", "es", "fr", "de"]
SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".m4v", ".webm"}
DEFAULT_QA_RETRIEVAL_LIMIT = 5
MAX_QA_RETRIEVAL_LIMIT = 8
DEFAULT_SEARCH_LIMIT = 20
DEFAULT_LIBRARY_SEARCH_LIMIT = 40
DEFAULT_LIBRARY_SUMMARY_CHARS = 240
WORD_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


class VideoRagError(RuntimeError):
    """User-facing pipeline error with an optional next-step hint."""

    def __init__(self, message: str, hint: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        if self.hint:
            return f"{self.message}\nNext step: {self.hint}"
        return self.message


@dataclass
class PipelineConfig:
    input_path: Path
    output_dir: Path
    model_size: str = DEFAULT_WHISPER_MODEL
    language: str = DEFAULT_LANGUAGE
    chunk_max_chars: int = DEFAULT_CHUNK_MAX_CHARS
    chunk_overlap_segments: int = DEFAULT_CHUNK_OVERLAP_SEGMENTS


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def ensure_path(value: Union[Path, str]) -> Path:
    if isinstance(value, Path):
        return value
    return Path(value)


def normalize_language(language: Optional[str]) -> str:
    if not language:
        return DEFAULT_LANGUAGE
    return language.strip().lower() or DEFAULT_LANGUAGE


def emit_log(
    message: str,
    *,
    log_callback: Optional[Callable[[str], None]] = None,
    echo: bool = True,
) -> None:
    if echo:
        print(message)
    if log_callback:
        log_callback(message)


def emit_progress(
    current_step: int,
    total_steps: int,
    message: str,
    *,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> None:
    if progress_callback:
        progress_callback(current_step, total_steps, message)


def format_seconds(seconds: Optional[float]) -> str:
    if seconds is None:
        return "unknown"
    total = max(0, int(round(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def run_cmd(
    cmd: list[str],
    *,
    log_callback: Optional[Callable[[str], None]] = None,
    echo_logs: bool = True,
    check: bool = True,
    capture: bool = True,
) -> str:
    emit_log(f"  CMD: {' '.join(str(x) for x in cmd)}", log_callback=log_callback, echo=echo_logs)
    result = subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        check=False,
    )
    if result.returncode != 0 and check:
        stderr = (result.stderr or "").strip()
        raise VideoRagError(
            "ffmpeg failed while processing the video.",
            hint=stderr[:300] or "Check whether the input video is playable and whether ffmpeg is installed correctly.",
        )
    return result.stdout if capture else ""


def ensure_runtime_ready() -> None:
    if shutil.which(FFMPEG_BIN) is None:
        raise VideoRagError(
            "ffmpeg is not installed or is not available in PATH.",
            hint="Install ffmpeg first. On macOS run `brew install ffmpeg`. On Ubuntu / Debian run `sudo apt install ffmpeg`.",
        )


def validate_input_path(input_path: Path) -> Path:
    input_str = str(input_path).strip()
    if input_str.startswith("http://") or input_str.startswith("https://"):
        raise VideoRagError(
            "URL inputs are not supported in this release.",
            hint="Download the video file locally first, then pass the local file path to video-rag.",
        )

    resolved = input_path.expanduser().resolve()
    if not resolved.exists():
        raise VideoRagError(
            f"Input file not found: {resolved}",
            hint="Check the file path and try again.",
        )
    if not resolved.is_file():
        raise VideoRagError(
            f"Input path is not a file: {resolved}",
            hint="Select a local video file such as .mp4, .mov, or .mkv.",
        )
    if resolved.suffix.lower() not in SUPPORTED_VIDEO_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_VIDEO_EXTENSIONS))
        raise VideoRagError(
            f"Unsupported file type: {resolved.suffix or 'unknown'}",
            hint=f"Use one of the supported formats: {supported}.",
        )
    return resolved


def is_cjk_char(char: str) -> bool:
    return "\u4e00" <= char <= "\u9fff"


def merge_segment_texts(texts: list[str]) -> str:
    merged = ""
    for raw_text in texts:
        text = raw_text.strip()
        if not text:
            continue
        if not merged:
            merged = text
            continue

        prev_char = merged[-1]
        next_char = text[0]

        if is_cjk_char(prev_char) or is_cjk_char(next_char):
            merged += text
        elif next_char in ".,!?;:)]}，。！？；：、":
            merged += text
        elif prev_char in "([{“\"'":
            merged += text
        else:
            merged += " " + text
    return merged


def estimate_token_count(text: str) -> int:
    cjk_chars = sum(1 for char in text if is_cjk_char(char))
    other_chars = sum(1 for char in text if not char.isspace() and not is_cjk_char(char))
    return max(1, math.ceil(cjk_chars / 1.5) + math.ceil(other_chars / 4))


def build_job_id(input_path: Path) -> str:
    raw = f"{input_path.stem}{os.path.getsize(input_path)}{datetime.now(CST).isoformat()}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def output_paths(output_dir: Path, job_id: str) -> dict:
    return {
        "audio_dir": output_dir / "audio",
        "transcript_dir": output_dir / "transcripts",
        "meta_dir": output_dir / "meta",
        "chunks_dir": output_dir / "chunks",
        "text_dir": output_dir / "text",
        "preview_dir": output_dir / "preview",
        "manifest_dir": output_dir / "manifests",
        "library_dir": output_dir / "library",
        "audio_path": output_dir / "audio" / f"{job_id}.wav",
        "transcript_path": output_dir / "transcripts" / f"{job_id}.json",
        "meta_path": output_dir / "meta" / f"{job_id}.meta.json",
        "chunk_path": output_dir / "chunks" / f"{job_id}.chunks.json",
        "text_path": output_dir / "text" / f"{job_id}.txt",
        "preview_path": output_dir / "preview" / f"{job_id}.md",
        "manifest_path": output_dir / "manifests" / f"{job_id}.manifest.json",
        "library_path": output_dir / "library" / f"{job_id}.video.json",
    }


def prepare_output_dirs(paths: dict) -> None:
    for key in [
        "audio_dir",
        "transcript_dir",
        "meta_dir",
        "chunks_dir",
        "text_dir",
        "preview_dir",
        "manifest_dir",
        "library_dir",
    ]:
        ensure_dir(paths[key])


def extract_audio(
    video_path: Path,
    audio_path: Path,
    *,
    log_callback: Optional[Callable[[str], None]] = None,
    echo_logs: bool = True,
) -> None:
    cmd = [
        FFMPEG_BIN,
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-loglevel",
        "error",
        str(audio_path),
    ]
    run_cmd(cmd, log_callback=log_callback, echo_logs=echo_logs, check=True)
    if not audio_path.exists():
        raise VideoRagError(
            "Audio extraction did not produce an output file.",
            hint="Check whether the input video contains a readable audio track.",
        )


def load_whisper_model(model_size: str):
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise VideoRagError(
            "Missing dependency: faster-whisper is not installed.",
            hint="Activate your virtual environment and run `pip install -r requirements.txt`.",
        ) from exc

    try:
        return WhisperModel(
            model_size,
            device="auto",
            compute_type=DEFAULT_COMPUTE_TYPE,
        )
    except Exception as exc:
        raise VideoRagError(
            f"Failed to load Whisper model '{model_size}'.",
            hint="Try a smaller model such as `base` or `small`, and make sure your machine can download the model files.",
        ) from exc


def transcribe(
    audio_path: Path,
    output_json: Path,
    *,
    model_size: str,
    language: str,
    log_callback: Optional[Callable[[str], None]] = None,
    echo_logs: bool = True,
) -> dict:
    emit_log(
        f"[Whisper] Loading model '{model_size}' (language={language})...",
        log_callback=log_callback,
        echo=echo_logs,
    )
    model = load_whisper_model(model_size)

    transcribe_kwargs = {
        "word_timestamps": True,
    }
    if language != DEFAULT_LANGUAGE:
        transcribe_kwargs["language"] = language

    emit_log(f"[Whisper] Transcribing {audio_path}...", log_callback=log_callback, echo=echo_logs)

    try:
        segments, info = model.transcribe(str(audio_path), **transcribe_kwargs)
    except Exception as exc:
        raise VideoRagError(
            "Transcription failed.",
            hint="Try a shorter clip, switch to a smaller model, or set the language manually if auto detection is unstable.",
        ) from exc

    emit_log(
        f"[Whisper] Detected language: {info.language} ({info.language_probability:.0%}), duration: {info.duration:.1f}s",
        log_callback=log_callback,
        echo=echo_logs,
    )

    transcript_data = {
        "model": model_size,
        "language": info.language,
        "duration_seconds": info.duration,
        "segments": [],
    }

    for seg in segments:
        seg_data = {
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
        }
        if hasattr(seg, "words") and seg.words:
            seg_data["words"] = [
                {
                    "word": word.word,
                    "start": round(word.start, 2),
                    "end": round(word.end, 2),
                    "probability": round(word.probability, 3),
                }
                for word in seg.words
            ]
        transcript_data["segments"].append(seg_data)

    with open(output_json, "w", encoding="utf-8") as file:
        json.dump(transcript_data, file, ensure_ascii=False, indent=2)

    emit_log(
        f"[Whisper] Saved: {output_json} ({len(transcript_data['segments'])} segments)",
        log_callback=log_callback,
        echo=echo_logs,
    )
    return transcript_data


def build_chunk_artifact(
    transcript_data: dict,
    metadata: dict,
    transcript_path: Path,
    meta_path: Path,
    chunk_path: Path,
    *,
    max_chars: int = DEFAULT_CHUNK_MAX_CHARS,
    overlap_segments: int = DEFAULT_CHUNK_OVERLAP_SEGMENTS,
) -> dict:
    segments = transcript_data.get("segments", [])
    chunks: list[dict] = []

    def make_chunk(segment_indexes: list[int], chunk_index: int) -> dict:
        chunk_segments = [segments[idx] for idx in segment_indexes]
        chunk_text = merge_segment_texts([segment["text"] for segment in chunk_segments])
        return {
            "chunk_id": f"{metadata['job_id']}-chunk-{chunk_index:03d}",
            "index": chunk_index,
            "start": round(chunk_segments[0]["start"], 2),
            "end": round(chunk_segments[-1]["end"], 2),
            "text": chunk_text,
            "char_count": len(chunk_text),
            "token_estimate": estimate_token_count(chunk_text),
            "segment_start_index": segment_indexes[0],
            "segment_end_index": segment_indexes[-1],
            "segment_count": len(segment_indexes),
            "prev_chunk_id": None,
            "next_chunk_id": None,
        }

    current_segment_indexes: list[int] = []
    chunk_index = 0
    segment_index = 0

    while segment_index < len(segments):
        if not current_segment_indexes:
            current_segment_indexes.append(segment_index)
            segment_index += 1
            continue

        candidate_indexes = current_segment_indexes + [segment_index]
        candidate_text = merge_segment_texts([segments[idx]["text"] for idx in candidate_indexes])
        if len(candidate_text) <= max_chars:
            current_segment_indexes = candidate_indexes
            segment_index += 1
            continue

        chunks.append(make_chunk(current_segment_indexes, chunk_index))
        chunk_index += 1

        overlap_count = min(overlap_segments, len(current_segment_indexes))
        overlap = current_segment_indexes[-overlap_count:] if overlap_count > 0 else []
        if len(overlap) == len(current_segment_indexes):
            overlap = []
        current_segment_indexes = overlap

    if current_segment_indexes:
        chunks.append(make_chunk(current_segment_indexes, chunk_index))

    for idx, chunk in enumerate(chunks):
        if idx > 0:
            chunk["prev_chunk_id"] = chunks[idx - 1]["chunk_id"]
        if idx < len(chunks) - 1:
            chunk["next_chunk_id"] = chunks[idx + 1]["chunk_id"]

    artifact = {
        "source_type": metadata["source_type"],
        "job_id": metadata["job_id"],
        "source_title": metadata["title"],
        "language": transcript_data.get("language"),
        "duration_seconds": transcript_data.get("duration_seconds"),
        "chunking_version": CHUNKING_VERSION,
        "chunking_strategy": CHUNKING_STRATEGY,
        "chunking_config": {
            "max_chars": max_chars,
            "overlap_segments": overlap_segments,
        },
        "source_transcript_path": str(transcript_path.resolve()),
        "source_meta_path": str(meta_path.resolve()),
        "chunk_count": len(chunks),
        "chunks": chunks,
    }

    with open(chunk_path, "w", encoding="utf-8") as file:
        json.dump(artifact, file, ensure_ascii=False, indent=2)

    return artifact


def build_readable_text(transcript_data: dict, *, paragraph_max_chars: int = 900) -> str:
    paragraphs: list[str] = []
    current_texts: list[str] = []
    current_chars = 0

    for segment in transcript_data.get("segments", []):
        text = segment.get("text", "").strip()
        if not text:
            continue
        candidate_chars = current_chars + len(text)
        if current_texts and candidate_chars > paragraph_max_chars:
            paragraphs.append(merge_segment_texts(current_texts))
            current_texts = [text]
            current_chars = len(text)
        else:
            current_texts.append(text)
            current_chars = candidate_chars

    if current_texts:
        paragraphs.append(merge_segment_texts(current_texts))

    return "\n\n".join(paragraphs).strip()


def build_chunk_preview_markdown(chunk_artifact: dict, *, max_chunks: int = 8) -> str:
    if not chunk_artifact.get("chunks"):
        return "_No chunks were generated._"

    lines = []
    for chunk in chunk_artifact["chunks"][:max_chunks]:
        lines.append(
            f"### Chunk {chunk['index'] + 1} · {format_seconds(chunk['start'])} - {format_seconds(chunk['end'])}"
        )
        lines.append(chunk["text"])
        lines.append("")

    if chunk_artifact["chunk_count"] > max_chunks:
        remaining = chunk_artifact["chunk_count"] - max_chunks
        lines.append(f"_... and {remaining} more chunks in the full JSON output._")

    return "\n".join(lines).strip()


def build_preview_markdown(
    metadata: dict,
    transcript_data: dict,
    chunk_artifact: dict,
    *,
    text_path: Path,
    preview_path: Path,
    manifest_path: Path,
) -> str:
    lines = [
        f"# {metadata['title']}",
        "",
        "Generated by `video-rag`.",
        "",
        "## At a glance",
        "",
        f"- Job ID: `{metadata['job_id']}`",
        f"- Created at: {metadata['created_at']}",
        f"- Model: `{metadata['whisper_model']}`",
        f"- Requested language: `{metadata['language_requested']}`",
        f"- Detected language: `{transcript_data.get('language', 'unknown')}`",
        f"- Duration: {format_seconds(transcript_data.get('duration_seconds'))}",
        f"- Transcript segments: {metadata['transcript_segments']}",
        f"- Chunks: {chunk_artifact['chunk_count']}",
        "",
        "## Open these first",
        "",
        f"1. `{preview_path.name}`: the easiest file for a first review",
        f"2. `{text_path.name}`: clean plain text if you just want to read or copy",
        f"3. `{manifest_path.name}`: machine-friendly summary of this run and all output paths",
        f"4. `{Path(metadata['library_path']).name}`: product-layer record for the personal video library",
        "",
        "## What each output file is for",
        "",
        f"- `{text_path.name}`: best for ordinary reading, quick copy, and note-taking",
        f"- `{preview_path.name}`: best for first review with chunk preview and output guide",
        f"- `{Path(metadata['transcript_path']).name}`: raw timestamped transcript JSON",
        f"- `{Path(metadata['chunk_path']).name}`: chunk-ready intermediate artifact for downstream indexing or retrieval",
        f"- `{Path(metadata['manifest_path']).name}`: one-file summary for apps and automation",
        f"- `{Path(metadata['library_path']).name}`: product-layer record for the local personal video library",
        f"- `{Path(metadata['audio_path']).name}`: extracted normalized audio",
        "",
        "## Chunk preview",
        "",
        build_chunk_preview_markdown(chunk_artifact),
    ]
    return "\n".join(lines).strip() + "\n"


def build_manifest(
    metadata: dict,
    transcript_data: dict,
    chunk_artifact: dict,
    *,
    text_path: Path,
    preview_path: Path,
    manifest_path: Path,
    library_path: Path,
) -> dict:
    return {
        "video_id": metadata["video_id"],
        "job_id": metadata["job_id"],
        "status": "completed",
        "source_type": metadata["source_type"],
        "source_title": metadata["title"],
        "language_requested": metadata["language_requested"],
        "language_detected": transcript_data.get("language"),
        "duration_seconds": transcript_data.get("duration_seconds"),
        "model": metadata["whisper_model"],
        "created_at": metadata["created_at"],
        "counts": {
            "segments": metadata["transcript_segments"],
            "chunks": chunk_artifact["chunk_count"],
        },
        "summary": {
            "start_here": str(preview_path.resolve()),
            "best_plain_text": str(text_path.resolve()),
            "download_recommendation": [
                "preview_markdown",
                "text_txt",
                "transcript_json",
                "chunks_json",
                "metadata_json",
                "manifest_json",
                "library_record_json",
            ],
        },
        "artifact_paths": {
            "audio_wav": metadata["audio_path"],
            "text_txt": str(text_path.resolve()),
            "preview_markdown": str(preview_path.resolve()),
            "transcript_json": metadata["transcript_path"],
            "chunks_json": metadata["chunk_path"],
            "metadata_json": metadata["meta_path"],
            "manifest_json": str(manifest_path.resolve()),
            "library_record_json": str(library_path.resolve()),
        },
        "artifact_descriptions": {
            "text_txt": "Best for ordinary reading, copy, and note-taking.",
            "preview_markdown": "Best first file for a guided review of the run.",
            "transcript_json": "Raw timestamped transcript for developer-facing processing.",
            "chunks_json": "Chunk-ready intermediate artifact for downstream indexing or retrieval.",
            "metadata_json": "Processing metadata that links source and generated artifacts.",
            "manifest_json": "One-file summary for UIs, automation, and downstream integrations.",
            "library_record_json": "Product-layer video library record for long-term local organization.",
        },
    }


def safe_load_json(path: Optional[Path]) -> Optional[dict]:
    if not path or not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return None


def safe_read_text(path: Optional[Path]) -> str:
    if not path or not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def resolve_path(path_value: Optional[str]) -> Optional[Path]:
    if not path_value:
        return None
    try:
        return Path(path_value).expanduser().resolve()
    except Exception:
        return None


def compact_text(text: str) -> str:
    return " ".join(text.split())


def build_summary_preview(
    text_content: str = "",
    chunk_artifact: Optional[dict] = None,
    *,
    max_chars: int = DEFAULT_LIBRARY_SUMMARY_CHARS,
) -> str:
    candidates: list[str] = []
    if text_content.strip():
        candidates.append(compact_text(text_content))
    if chunk_artifact:
        chunk_texts = [chunk.get("text", "") for chunk in chunk_artifact.get("chunks", [])[:2] if chunk.get("text")]
        if chunk_texts:
            candidates.append(compact_text(" ".join(chunk_texts)))

    for candidate in candidates:
        if candidate:
            if len(candidate) <= max_chars:
                return candidate
            return candidate[: max_chars - 3].rstrip() + "..."
    return ""


def normalize_tags(tags_value: Union[str, list, None]) -> list[str]:
    if isinstance(tags_value, list):
        raw_tags = tags_value
    elif isinstance(tags_value, str):
        raw_tags = re.split(r"[,，\n]+", tags_value)
    else:
        raw_tags = []

    tags: list[str] = []
    seen: set[str] = set()
    for raw in raw_tags:
        tag = compact_text(str(raw).strip())
        if not tag:
            continue
        lowered = tag.lower()
        if lowered in seen:
            continue
        tags.append(tag)
        seen.add(lowered)
    return tags


def library_record_path(data_dir: Union[Path, str], video_id: str) -> Path:
    return ensure_path(data_dir) / "library" / f"{video_id}.video.json"


def export_record_from_path(export_path: Path) -> dict:
    export_name = export_path.stem
    export_type = export_name.split("-", 1)[0] if "-" in export_name else "export"
    created_at = datetime.fromtimestamp(export_path.stat().st_mtime, tz=CST).isoformat()
    return {
        "export_id": export_name,
        "type": export_type,
        "path": str(export_path.resolve()),
        "created_at": created_at,
    }


def list_saved_exports_from_disk(data_dir: Union[Path, str], video_id: str) -> list[dict]:
    exports_dir = ensure_path(data_dir) / "exports" / video_id
    if not exports_dir.exists():
        return []

    return [
        export_record_from_path(path)
        for path in sorted(exports_dir.glob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True)
        if path.is_file()
    ]


def merge_saved_exports(existing_exports: list[dict], disk_exports: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for record in existing_exports + disk_exports:
        export_path = resolve_path(record.get("path"))
        if export_path and export_path.exists():
            normalized = export_record_from_path(export_path)
        else:
            normalized = {
                "export_id": str(record.get("export_id", "")),
                "type": str(record.get("type", "export")),
                "path": str(record.get("path", "")),
                "created_at": str(record.get("created_at", "")),
            }
        if normalized["path"]:
            merged[normalized["path"]] = normalized

    return sorted(merged.values(), key=lambda item: parse_created_at(item["created_at"]), reverse=True)


def contains_cjk(text: str) -> bool:
    return any(is_cjk_char(char) for char in text)


def tokenize_search_text(text: str) -> list[str]:
    return [token.lower() for token in WORD_RE.findall(text)]


def cjk_ngrams(text: str, size: int = 2) -> set[str]:
    chars = [char for char in text if is_cjk_char(char)]
    if len(chars) < size:
        return {"".join(chars)} if chars else set()
    return {"".join(chars[index:index + size]) for index in range(len(chars) - size + 1)}


def parse_created_at(value: Optional[str]) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=CST)
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return datetime.min.replace(tzinfo=CST)


def format_duration_for_record(seconds: Optional[float]) -> str:
    return format_seconds(seconds)


def timestamp_slug() -> str:
    return datetime.now(CST).strftime("%Y%m%d-%H%M%S")


def sanitize_filename_part(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip())
    return cleaned.strip("-._") or "video"


def build_match_snippet(text: str, match_start: int = 0, match_end: int = 0, radius: int = 80) -> str:
    if not text:
        return ""
    start = max(0, match_start - radius)
    end = min(len(text), max(match_end, match_start) + radius)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet


def score_chunk_text(query: str, chunk_text: str) -> tuple[int, str]:
    query_raw = query.strip()
    text_raw = chunk_text.strip()
    if not query_raw or not text_raw:
        return 0, ""

    query_text = compact_text(query_raw).lower()
    normalized_text = compact_text(text_raw)
    haystack = normalized_text.lower()

    score = 0
    match_start = 0
    match_end = 0

    phrase_hits = haystack.count(query_text) if query_text else 0
    if phrase_hits:
        score += 120 + phrase_hits * 25
        match_start = haystack.find(query_text)
        match_end = match_start + len(query_text)

    query_tokens = tokenize_search_text(query_text)
    haystack_tokens = tokenize_search_text(haystack)
    if query_tokens and haystack_tokens:
        haystack_token_set = set(haystack_tokens)
        overlap = [token for token in dict.fromkeys(query_tokens) if token in haystack_token_set]
        if overlap:
            score += len(overlap) * 18
            if not match_end:
                token = overlap[0]
                match_start = haystack.find(token)
                match_end = match_start + len(token)

    if contains_cjk(query_raw):
        query_ngrams = cjk_ngrams(query_raw)
        text_ngrams = cjk_ngrams(text_raw)
        if query_ngrams and text_ngrams:
            ngram_overlap = query_ngrams & text_ngrams
            if ngram_overlap:
                score += len(ngram_overlap) * 10
                if not match_end:
                    first = sorted(ngram_overlap, key=len, reverse=True)[0]
                    match_start = text_raw.find(first)
                    match_end = match_start + len(first)

    if score <= 0:
        return 0, ""

    snippet = build_match_snippet(text_raw, match_start=max(0, match_start), match_end=max(match_end, match_start + 1))
    return score, snippet


def search_chunk_artifact(query: str, chunk_artifact: dict, *, limit: int = DEFAULT_SEARCH_LIMIT) -> list[dict]:
    if not query.strip():
        return []

    results: list[dict] = []
    for chunk in chunk_artifact.get("chunks", []):
        score, snippet = score_chunk_text(query, chunk.get("text", ""))
        if score <= 0:
            continue
        results.append(
            {
                "result_id": f"{chunk['chunk_id']}-result",
                "chunk_id": chunk["chunk_id"],
                "chunk_index": chunk["index"],
                "start": chunk["start"],
                "end": chunk["end"],
                "text": chunk.get("text", ""),
                "match_snippet": snippet,
                "score": score,
            }
        )

    results.sort(key=lambda item: (-item["score"], item["start"], item["chunk_index"]))
    return results[:limit]


def build_library_record(
    *,
    data_dir: Union[Path, str],
    manifest: dict,
    metadata: dict,
    chunk_artifact: Optional[dict],
    text_content: str,
    existing_record: Optional[dict] = None,
) -> dict:
    data_dir = ensure_path(data_dir)
    video_id = manifest.get("video_id") or metadata.get("video_id") or manifest.get("job_id") or metadata.get("job_id")
    title = metadata.get("title") or manifest.get("source_title") or video_id
    artifact_paths = dict(manifest.get("artifact_paths") or {})
    artifact_paths.setdefault("manifest_json", metadata.get("manifest_path") or "")
    artifact_paths.setdefault("metadata_json", metadata.get("meta_path") or "")
    artifact_paths.setdefault("transcript_json", metadata.get("transcript_path") or "")
    artifact_paths.setdefault("chunks_json", metadata.get("chunk_path") or "")
    artifact_paths.setdefault("text_txt", metadata.get("text_path") or "")
    artifact_paths.setdefault("preview_markdown", metadata.get("preview_path") or "")
    artifact_paths["exports_dir"] = str((data_dir / "exports" / video_id).resolve())
    artifact_paths["library_record_json"] = str(library_record_path(data_dir, video_id).resolve())

    existing = existing_record or {}
    return {
        "video_id": video_id,
        "job_id": manifest.get("job_id") or metadata.get("job_id") or video_id,
        "title": title,
        "display_title": compact_text(str(existing.get("display_title") or title)),
        "created_at": manifest.get("created_at") or metadata.get("created_at"),
        "updated_at": existing.get("updated_at") or manifest.get("created_at") or metadata.get("created_at"),
        "duration_seconds": manifest.get("duration_seconds") or metadata.get("transcript_duration_seconds"),
        "language": manifest.get("language_detected") or metadata.get("language_detected") or "unknown",
        "status": manifest.get("status", "completed"),
        "summary": build_summary_preview(text_content, chunk_artifact),
        "tags": normalize_tags(existing.get("tags")),
        "starred": bool(existing.get("starred", False)),
        "notes": str(existing.get("notes", "")),
        "source_file_path": metadata.get("input_path") or "",
        "artifact_paths": artifact_paths,
        "saved_exports": merge_saved_exports(existing.get("saved_exports", []), list_saved_exports_from_disk(data_dir, video_id)),
    }


def sync_library_record(video_id: str, data_dir: Union[Path, str]) -> dict:
    data_dir = ensure_path(data_dir)
    manifest_path = (data_dir / "manifests" / f"{video_id}.manifest.json").resolve()
    manifest = safe_load_json(manifest_path)
    if not manifest:
        raise VideoRagError(
            f"Manifest not found for video: {video_id}",
            hint="Process the video again or refresh the library.",
        )

    artifact_paths = dict(manifest.get("artifact_paths") or {})
    meta_path = resolve_path(artifact_paths.get("metadata_json")) or (data_dir / "meta" / f"{video_id}.meta.json").resolve()
    metadata = safe_load_json(meta_path) or {}
    chunk_artifact = safe_load_json(resolve_path(artifact_paths.get("chunks_json")))
    text_content = safe_read_text(resolve_path(artifact_paths.get("text_txt")))
    existing_record = safe_load_json(library_record_path(data_dir, video_id))
    record = build_library_record(
        data_dir=data_dir,
        manifest=manifest,
        metadata=metadata,
        chunk_artifact=chunk_artifact,
        text_content=text_content,
        existing_record=existing_record,
    )
    write_json(library_record_path(data_dir, video_id), record)
    return record


def ensure_library_records(data_dir: Union[Path, str]) -> None:
    data_dir = ensure_path(data_dir)
    manifests_dir = data_dir / "manifests"
    ensure_dir(data_dir / "library")
    if not manifests_dir.exists():
        return

    for manifest_path in manifests_dir.glob("*.manifest.json"):
        manifest = safe_load_json(manifest_path) or {}
        video_id = manifest.get("video_id") or manifest.get("job_id") or manifest_path.stem.replace(".manifest", "")
        sync_library_record(video_id, data_dir)


def load_video_library_records(data_dir: Union[Path, str]) -> list[dict]:
    data_dir = ensure_path(data_dir)
    ensure_library_records(data_dir)

    library_dir = data_dir / "library"
    if not library_dir.exists():
        return []

    records = []
    for record_path in library_dir.glob("*.video.json"):
        record = safe_load_json(record_path)
        if not record:
            continue
        record.setdefault("display_title", record.get("title") or record.get("video_id"))
        record.setdefault("tags", [])
        record.setdefault("starred", False)
        record.setdefault("notes", "")
        record.setdefault("saved_exports", [])
        records.append(record)

    records.sort(key=lambda item: parse_created_at(item.get("created_at")), reverse=True)
    return records


def update_library_record(
    data_dir: Union[Path, str],
    video_id: str,
    *,
    display_title: Optional[str] = None,
    tags: Optional[Union[str, list]] = None,
    notes: Optional[str] = None,
    starred: Optional[bool] = None,
) -> dict:
    data_dir = ensure_path(data_dir)
    record = safe_load_json(library_record_path(data_dir, video_id)) or sync_library_record(video_id, data_dir)
    if display_title is not None:
        record["display_title"] = compact_text(display_title.strip()) or record.get("title") or video_id
    if tags is not None:
        record["tags"] = normalize_tags(tags)
    if notes is not None:
        record["notes"] = notes.strip()
    if starred is not None:
        record["starred"] = bool(starred)
    record["updated_at"] = datetime.now(CST).isoformat()
    write_json(library_record_path(data_dir, video_id), record)
    return record


def append_saved_export(data_dir: Union[Path, str], video_id: str, export_type: str, export_path: Union[Path, str]) -> dict:
    data_dir = ensure_path(data_dir)
    export_file = ensure_path(export_path)
    record = safe_load_json(library_record_path(data_dir, video_id)) or sync_library_record(video_id, data_dir)
    saved_exports = record.get("saved_exports", [])
    normalized = export_record_from_path(export_file)
    normalized["type"] = export_type
    saved_exports = [item for item in saved_exports if item.get("path") != normalized["path"]]
    saved_exports.insert(0, normalized)
    record["saved_exports"] = merge_saved_exports(saved_exports, list_saved_exports_from_disk(data_dir, video_id))
    record["updated_at"] = datetime.now(CST).isoformat()
    write_json(library_record_path(data_dir, video_id), record)
    return record


def filter_video_library_records(
    records: list[dict],
    *,
    title_query: str = "",
    language: str = "all",
    starred: str = "all",
    sort_order: str = "recent_desc",
) -> list[dict]:
    title_query_norm = title_query.strip().lower()
    filtered = []
    for record in records:
        haystack = " ".join(
            [
                str(record.get("display_title", "")),
                str(record.get("title", "")),
                " ".join(record.get("tags", [])),
            ]
        ).lower()
        if title_query_norm and title_query_norm not in haystack:
            continue
        if language != "all" and record.get("language") != language:
            continue
        if starred == "starred" and not record.get("starred"):
            continue
        if starred == "unstarred" and record.get("starred"):
            continue
        filtered.append(record)

    if sort_order == "recent_asc":
        filtered.sort(key=lambda item: parse_created_at(item.get("created_at")))
    elif sort_order == "title_asc":
        filtered.sort(key=lambda item: str(item.get("display_title") or item.get("title") or "").lower())
    else:
        filtered.sort(key=lambda item: parse_created_at(item.get("created_at")), reverse=True)
    return filtered


def search_video_library(
    query: str,
    records: list[dict],
    *,
    limit: int = DEFAULT_LIBRARY_SEARCH_LIMIT,
) -> list[dict]:
    query_text = query.strip()
    if not query_text:
        return []

    results: list[dict] = []
    for record in records:
        chunk_artifact = safe_load_json(resolve_path(record.get("artifact_paths", {}).get("chunks_json"))) or {"chunks": []}
        video_boost = 0
        for field_text in [
            str(record.get("display_title", "")),
            str(record.get("title", "")),
            " ".join(record.get("tags", [])),
            str(record.get("notes", "")),
            str(record.get("summary", "")),
        ]:
            field_score, _ = score_chunk_text(query_text, field_text)
            video_boost += min(field_score, 6)

        for chunk in chunk_artifact.get("chunks", []):
            chunk_score, snippet = score_chunk_text(query_text, chunk.get("text", ""))
            if chunk_score <= 0:
                continue
            results.append(
                {
                    "result_id": f"{record['video_id']}::{chunk['chunk_id']}",
                    "video_id": record["video_id"],
                    "display_title": record.get("display_title") or record.get("title") or record["video_id"],
                    "chunk_id": chunk["chunk_id"],
                    "chunk_index": chunk["index"],
                    "start": chunk["start"],
                    "end": chunk["end"],
                    "match_snippet": snippet or chunk.get("text", "")[:120],
                    "summary_preview": record.get("summary", ""),
                    "score": chunk_score + video_boost,
                    "created_at": record.get("created_at"),
                }
            )

    results.sort(key=lambda item: (-item["score"], parse_created_at(item.get("created_at")), item["start"]))
    return results[:limit]


def load_history_records(data_dir: Union[Path, str]) -> list[dict]:
    data_dir = ensure_path(data_dir)
    manifests_dir = data_dir / "manifests"
    if not manifests_dir.exists():
        return []

    records: list[dict] = []
    for manifest_path in sorted(manifests_dir.glob("*.manifest.json")):
        manifest = safe_load_json(manifest_path) or {}
        artifact_paths = manifest.get("artifact_paths", {})
        meta_path = resolve_path(artifact_paths.get("metadata_json"))
        metadata = safe_load_json(meta_path) or {}
        counts = manifest.get("counts") or {}

        duration_seconds = manifest.get("duration_seconds")
        if duration_seconds is None:
            duration_seconds = metadata.get("transcript_duration_seconds")

        record = {
            "job_id": manifest.get("job_id") or manifest_path.stem.replace(".manifest", ""),
            "source_title": manifest.get("source_title") or metadata.get("title") or manifest_path.stem,
            "created_at": manifest.get("created_at") or metadata.get("created_at"),
            "duration_seconds": duration_seconds,
            "duration_label": format_duration_for_record(duration_seconds),
            "language_detected": manifest.get("language_detected") or metadata.get("language_detected") or "unknown",
            "segments": counts.get("segments", metadata.get("transcript_segments", 0)),
            "chunks": counts.get("chunks", metadata.get("chunk_count", 0)),
            "status": manifest.get("status", "completed"),
            "manifest_path": str(manifest_path.resolve()),
            "artifact_paths": artifact_paths,
        }
        records.append(record)

    records.sort(key=lambda item: parse_created_at(item["created_at"]), reverse=True)
    return records


def load_video_bundle(job_id: str, data_dir: Union[Path, str]) -> dict:
    data_dir = ensure_path(data_dir)
    video_id = job_id
    sync_library_record(video_id, data_dir)
    manifest_path = (data_dir / "manifests" / f"{video_id}.manifest.json").resolve()
    manifest = safe_load_json(manifest_path)
    if not manifest:
        raise VideoRagError(
            f"Manifest not found for job: {video_id}",
            hint="Process the video again or refresh the library.",
        )

    artifact_paths = manifest.get("artifact_paths", {})
    meta_path = resolve_path(artifact_paths.get("metadata_json"))
    chunk_path = resolve_path(artifact_paths.get("chunks_json"))
    transcript_path = resolve_path(artifact_paths.get("transcript_json"))
    text_path = resolve_path(artifact_paths.get("text_txt"))
    preview_path = resolve_path(artifact_paths.get("preview_markdown"))
    library_path = resolve_path(artifact_paths.get("library_record_json")) or library_record_path(data_dir, video_id)

    metadata = safe_load_json(meta_path) or {}
    chunk_artifact = safe_load_json(chunk_path)
    transcript = safe_load_json(transcript_path) or {}
    library_record = safe_load_json(library_path) or {}
    if not chunk_artifact:
        chunk_artifact = {
            "job_id": video_id,
            "chunk_count": 0,
            "chunks": [],
        }

    chunk_map = {chunk["chunk_id"]: chunk for chunk in chunk_artifact.get("chunks", [])}
    return {
        "video_id": video_id,
        "job_id": manifest.get("job_id") or video_id,
        "manifest": manifest,
        "library_record": library_record,
        "metadata": metadata,
        "transcript": transcript,
        "chunks": chunk_artifact,
        "chunk_map": chunk_map,
        "content_ready": bool(chunk_artifact.get("chunks")),
        "text_content": safe_read_text(text_path),
        "preview_content": safe_read_text(preview_path),
        "artifact_paths": artifact_paths,
        "paths": {
            "manifest_path": str(manifest_path),
            "meta_path": str(meta_path) if meta_path else "",
            "chunk_path": str(chunk_path) if chunk_path else "",
            "transcript_path": str(transcript_path) if transcript_path else "",
            "text_path": str(text_path) if text_path else "",
            "preview_path": str(preview_path) if preview_path else "",
            "library_path": str(library_path) if library_path else "",
            "exports_dir": str((data_dir / "exports" / video_id).resolve()),
        },
    }


def build_qa_endpoint(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    return normalized + "/chat/completions"


def extract_message_text(message: dict) -> str:
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "\n".join(part for part in parts if part).strip()
    return ""


def extract_json_object(text: str) -> dict:
    fenced = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text)
    if fenced:
        return json.loads(fenced.group(1))

    start = text.find("{")
    if start < 0:
        raise ValueError("No JSON object found in model response.")

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == "\"":
                in_string = False
            continue

        if char == "\"":
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:index + 1])

    raise ValueError("Incomplete JSON object in model response.")


def call_openai_compatible_chat(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict],
    temperature: float = 0.2,
    timeout: int = 90,
) -> dict:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    request = urllib.request.Request(
        build_qa_endpoint(base_url),
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise VideoRagError(
            f"QA request failed with HTTP {exc.code}.",
            hint=body[:500] or "Check the QA base URL, model, and API key.",
        ) from exc
    except urllib.error.URLError as exc:
        raise VideoRagError(
            "Could not reach the QA model endpoint.",
            hint="Check the QA base URL and your network connection.",
        ) from exc


def run_grounded_qa(
    *,
    question: str,
    video_bundle: dict,
    base_url: str,
    model: str,
    api_key: str,
    top_k: int = DEFAULT_QA_RETRIEVAL_LIMIT,
) -> dict:
    question_text = question.strip()
    if not question_text:
        raise VideoRagError("Question cannot be empty.")
    if not base_url.strip() or not model.strip() or not api_key.strip():
        raise VideoRagError(
            "QA configuration is incomplete.",
            hint="Set QA base URL, model, and API key before asking a question.",
        )

    retrieval_limit = max(1, min(top_k, MAX_QA_RETRIEVAL_LIMIT))
    search_results = search_chunk_artifact(question_text, video_bundle["chunks"], limit=MAX_QA_RETRIEVAL_LIMIT)
    if not search_results:
        return {
            "question": question_text,
            "answer": "当前视频内容中没有足够依据来回答这个问题。",
            "citations": [],
            "insufficient_evidence": True,
            "retrieved_results": [],
        }

    retrieved_results = search_results[:retrieval_limit]
    evidence_blocks = []
    for result in retrieved_results:
        chunk = video_bundle["chunk_map"][result["chunk_id"]]
        evidence_blocks.append(
            {
                "chunk_id": chunk["chunk_id"],
                "chunk_index": chunk["index"],
                "start": chunk["start"],
                "end": chunk["end"],
                "text": chunk["text"],
            }
        )

    system_prompt = (
        "You answer questions using ONLY the provided video evidence.\n"
        "Return valid JSON only.\n"
        "If the evidence is insufficient, set `insufficient_evidence` to true, give a short answer saying there is not enough evidence, and return an empty citations array.\n"
        "If the evidence is sufficient, keep the answer grounded and concise. Every citation must refer to one of the provided chunk_ids."
    )
    user_prompt = {
        "question": question_text,
        "video": {
            "title": video_bundle["manifest"].get("source_title") or video_bundle["metadata"].get("title"),
            "language": video_bundle["manifest"].get("language_detected"),
            "duration_seconds": video_bundle["manifest"].get("duration_seconds"),
        },
        "evidence_chunks": evidence_blocks,
        "required_output_schema": {
            "answer": "string",
            "insufficient_evidence": "boolean",
            "citations": [
                {
                    "chunk_id": "string",
                    "chunk_index": "integer",
                    "start": "number",
                    "end": "number",
                    "support_summary": "string",
                }
            ],
        },
    }

    response = call_openai_compatible_chat(
        base_url=base_url,
        api_key=api_key,
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_prompt, ensure_ascii=False, indent=2)},
        ],
    )
    try:
        message = response["choices"][0]["message"]
        parsed = extract_json_object(extract_message_text(message))
    except Exception as exc:
        raise VideoRagError(
            "The QA model returned an unreadable response.",
            hint="Try the question again, or switch to a model that reliably returns JSON.",
        ) from exc

    valid_chunk_ids = set(video_bundle["chunk_map"].keys())
    citations = []
    for citation in parsed.get("citations", []) or []:
        chunk_id = citation.get("chunk_id")
        if chunk_id not in valid_chunk_ids:
            continue
        chunk = video_bundle["chunk_map"][chunk_id]
        citations.append(
            {
                "chunk_id": chunk_id,
                "chunk_index": chunk["index"],
                "start": chunk["start"],
                "end": chunk["end"],
                "support_summary": compact_text(str(citation.get("support_summary", "")).strip()) or chunk["text"][:120],
            }
        )

    insufficient_evidence = bool(parsed.get("insufficient_evidence"))
    answer = compact_text(str(parsed.get("answer", "")).strip())
    if insufficient_evidence or not citations:
        answer = answer or "当前视频内容中没有足够依据来回答这个问题。"
        return {
            "question": question_text,
            "answer": answer,
            "citations": [],
            "insufficient_evidence": True,
            "retrieved_results": retrieved_results,
        }

    return {
        "question": question_text,
        "answer": answer,
        "citations": citations,
        "insufficient_evidence": False,
        "retrieved_results": retrieved_results,
    }


def export_directory(data_dir: Union[Path, str], job_id: str) -> Path:
    data_dir = ensure_path(data_dir)
    exports_dir = data_dir / "exports" / job_id
    ensure_dir(exports_dir)
    return exports_dir


def export_search_results(data_dir: Union[Path, str], video_bundle: dict, query: str, results: list[dict]) -> Path:
    exports_dir = export_directory(data_dir, video_bundle["job_id"])
    filename = exports_dir / f"search-{timestamp_slug()}.md"
    lines = [
        f"# Search results · {video_bundle['manifest'].get('source_title')}",
        "",
        f"- Query: `{query}`",
        f"- Match count: {len(results)}",
        "",
    ]
    if not results:
        lines.append("No matches found.")
    else:
        for result in results:
            lines.extend(
                [
                    f"## Chunk {result['chunk_index'] + 1} · {format_seconds(result['start'])} - {format_seconds(result['end'])}",
                    "",
                    result["match_snippet"] or result["text"],
                    "",
                ]
            )
    write_text(filename, "\n".join(lines).strip() + "\n")
    append_saved_export(data_dir, video_bundle["video_id"], "search", filename)
    return filename


def export_qa_result(data_dir: Union[Path, str], video_bundle: dict, qa_result: dict) -> Path:
    exports_dir = export_directory(data_dir, video_bundle["job_id"])
    filename = exports_dir / f"qa-{timestamp_slug()}.md"
    lines = [
        f"# QA result · {video_bundle['manifest'].get('source_title')}",
        "",
        f"## Question",
        "",
        qa_result["question"],
        "",
        "## Answer",
        "",
        qa_result["answer"],
        "",
        "## Citations",
        "",
    ]
    if not qa_result.get("citations"):
        lines.append("No citations available.")
    else:
        for citation in qa_result["citations"]:
            lines.extend(
                [
                    f"- Chunk {citation['chunk_index'] + 1} · {format_seconds(citation['start'])} - {format_seconds(citation['end'])}",
                    f"  {citation['support_summary']}",
                ]
            )
    write_text(filename, "\n".join(lines).strip() + "\n")
    append_saved_export(data_dir, video_bundle["video_id"], "qa", filename)
    return filename


def export_video_summary(data_dir: Union[Path, str], video_bundle: dict) -> Path:
    exports_dir = export_directory(data_dir, video_bundle["job_id"])
    filename = exports_dir / f"summary-{timestamp_slug()}.md"
    manifest = video_bundle["manifest"]
    chunks = video_bundle["chunks"].get("chunks", [])
    lines = [
        f"# Video summary · {manifest.get('source_title')}",
        "",
        "## Overview",
        "",
        f"- Language: `{manifest.get('language_detected', 'unknown')}`",
        f"- Duration: `{format_seconds(manifest.get('duration_seconds'))}`",
        f"- Segments: `{manifest.get('counts', {}).get('segments', 0)}`",
        f"- Chunks: `{manifest.get('counts', {}).get('chunks', 0)}`",
        "",
        "## Chunk overview",
        "",
    ]
    if not chunks:
        lines.append("No chunks available.")
    else:
        for chunk in chunks[:12]:
            lines.extend(
                [
                    f"### Chunk {chunk['index'] + 1} · {format_seconds(chunk['start'])} - {format_seconds(chunk['end'])}",
                    chunk["text"],
                    "",
                ]
            )
        if len(chunks) > 12:
            lines.append(f"_... and {len(chunks) - 12} more chunks in the full chunk artifact._")
    write_text(filename, "\n".join(lines).strip() + "\n")
    append_saved_export(data_dir, video_bundle["video_id"], "summary", filename)
    return filename


def write_json(path: Path, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def write_text(path: Path, text: str) -> None:
    with open(path, "w", encoding="utf-8") as file:
        file.write(text)


def run_pipeline(
    config: PipelineConfig,
    *,
    log_callback: Optional[Callable[[str], None]] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    echo_logs: bool = True,
) -> dict:
    total_steps = 6
    emit_progress(0, total_steps, "Checking runtime dependencies", progress_callback=progress_callback)
    ensure_runtime_ready()

    input_path = validate_input_path(config.input_path)
    language = normalize_language(config.language)
    if config.chunk_max_chars < 1:
        raise VideoRagError("--chunk-max-chars must be a positive integer.")
    if config.chunk_overlap_segments < 0:
        raise VideoRagError("--chunk-overlap-segments must be zero or greater.")

    output_dir = config.output_dir.expanduser().resolve()
    job_id = build_job_id(input_path)
    paths = output_paths(output_dir, job_id)
    prepare_output_dirs(paths)

    emit_log(f"\n=== Processing local video: {input_path} ===", log_callback=log_callback, echo=echo_logs)

    emit_progress(1, total_steps, "Extracting audio", progress_callback=progress_callback)
    emit_log(
        f"\n[Step 1/6] Extracting audio -> {paths['audio_path']}",
        log_callback=log_callback,
        echo=echo_logs,
    )
    extract_audio(
        input_path,
        paths["audio_path"],
        log_callback=log_callback,
        echo_logs=echo_logs,
    )

    emit_progress(2, total_steps, "Running transcription", progress_callback=progress_callback)
    emit_log(
        f"\n[Step 2/6] Transcribing -> {paths['transcript_path']}",
        log_callback=log_callback,
        echo=echo_logs,
    )
    transcript_data = transcribe(
        paths["audio_path"],
        paths["transcript_path"],
        model_size=config.model_size,
        language=language,
        log_callback=log_callback,
        echo_logs=echo_logs,
    )

    emit_progress(3, total_steps, "Writing metadata", progress_callback=progress_callback)
    emit_log("\n[Step 3/6] Writing metadata", log_callback=log_callback, echo=echo_logs)
    metadata = {
        "job_id": job_id,
        "video_id": job_id,
        "source_type": "local_video",
        "platform": "local",
        "input_path": str(input_path.resolve()),
        "input_size_bytes": os.path.getsize(input_path),
        "video_id": None,
        "title": input_path.stem,
        "caption": None,
        "audio_path": str(paths["audio_path"].resolve()),
        "transcript_path": str(paths["transcript_path"].resolve()),
        "transcript_segments": len(transcript_data["segments"]),
        "transcript_duration_seconds": transcript_data.get("duration_seconds"),
        "language_requested": language,
        "language_detected": transcript_data.get("language"),
        "whisper_model": transcript_data.get("model"),
        "created_at": datetime.now(CST).isoformat(),
    }
    write_json(paths["meta_path"], metadata)

    emit_progress(4, total_steps, "Building chunks", progress_callback=progress_callback)
    emit_log("\n[Step 4/6] Writing chunk-ready artifact", log_callback=log_callback, echo=echo_logs)
    chunk_artifact = build_chunk_artifact(
        transcript_data,
        metadata,
        paths["transcript_path"],
        paths["meta_path"],
        paths["chunk_path"],
        max_chars=config.chunk_max_chars,
        overlap_segments=config.chunk_overlap_segments,
    )

    emit_progress(5, total_steps, "Preparing readable outputs", progress_callback=progress_callback)
    emit_log("\n[Step 5/6] Writing readable text outputs", log_callback=log_callback, echo=echo_logs)
    transcript_text = build_readable_text(transcript_data)
    write_text(paths["text_path"], transcript_text + ("\n" if transcript_text else ""))

    metadata["chunk_path"] = str(paths["chunk_path"].resolve())
    metadata["chunk_count"] = chunk_artifact["chunk_count"]
    metadata["chunking_strategy"] = chunk_artifact["chunking_strategy"]
    metadata["chunking_version"] = chunk_artifact["chunking_version"]
    metadata["text_path"] = str(paths["text_path"].resolve())
    metadata["preview_path"] = str(paths["preview_path"].resolve())
    metadata["manifest_path"] = str(paths["manifest_path"].resolve())
    metadata["meta_path"] = str(paths["meta_path"].resolve())
    metadata["library_path"] = str(paths["library_path"].resolve())

    preview_markdown = build_preview_markdown(
        metadata,
        transcript_data,
        chunk_artifact,
        text_path=paths["text_path"],
        preview_path=paths["preview_path"],
        manifest_path=paths["manifest_path"],
    )
    write_text(paths["preview_path"], preview_markdown)

    emit_progress(6, total_steps, "Writing manifest", progress_callback=progress_callback)
    emit_log("\n[Step 6/6] Writing run manifest", log_callback=log_callback, echo=echo_logs)
    manifest = build_manifest(
        metadata,
        transcript_data,
        chunk_artifact,
        text_path=paths["text_path"],
        preview_path=paths["preview_path"],
        manifest_path=paths["manifest_path"],
        library_path=paths["library_path"],
    )
    write_json(paths["manifest_path"], manifest)
    library_record = sync_library_record(job_id, config.output_dir)
    write_json(paths["meta_path"], metadata)

    emit_log(f"[Done] Manifest saved: {paths['manifest_path']}", log_callback=log_callback, echo=echo_logs)
    emit_progress(total_steps, total_steps, "Completed", progress_callback=progress_callback)

    return {
        "job_id": job_id,
        "metadata": metadata,
        "transcript": transcript_data,
        "chunks": chunk_artifact,
        "manifest": manifest,
        "library_record": library_record,
        "transcript_text": transcript_text,
        "preview_markdown": preview_markdown,
    }


def process_local_mp4(
    mp4_path: Path,
    output_dir: Path,
    model_size: str = DEFAULT_WHISPER_MODEL,
    language: str = DEFAULT_LANGUAGE,
    chunk_max_chars: int = DEFAULT_CHUNK_MAX_CHARS,
    chunk_overlap_segments: int = DEFAULT_CHUNK_OVERLAP_SEGMENTS,
) -> dict:
    result = run_pipeline(
        PipelineConfig(
            input_path=mp4_path,
            output_dir=output_dir,
            model_size=model_size,
            language=language,
            chunk_max_chars=chunk_max_chars,
            chunk_overlap_segments=chunk_overlap_segments,
        )
    )
    return result["metadata"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="video-rag local video pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--input", "-i", required=True, help="Downloaded local video file path")
    parser.add_argument("--output-dir", "-o", default="./data", help="Output root directory (default: ./data)")
    parser.add_argument(
        "--model",
        "-m",
        default=DEFAULT_WHISPER_MODEL,
        choices=SUPPORTED_MODELS,
        help=f"Whisper model (default: {DEFAULT_WHISPER_MODEL})",
    )
    parser.add_argument(
        "--language",
        default=DEFAULT_LANGUAGE,
        help="Language code such as zh or en, or 'auto' for detection (default: auto)",
    )
    parser.add_argument(
        "--chunk-max-chars",
        type=int,
        default=DEFAULT_CHUNK_MAX_CHARS,
        help=f"Approximate character limit per chunk (default: {DEFAULT_CHUNK_MAX_CHARS})",
    )
    parser.add_argument(
        "--chunk-overlap-segments",
        type=int,
        default=DEFAULT_CHUNK_OVERLAP_SEGMENTS,
        help=f"How many transcript segments to overlap between chunks (default: {DEFAULT_CHUNK_OVERLAP_SEGMENTS})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        result = run_pipeline(
            PipelineConfig(
                input_path=Path(args.input),
                output_dir=Path(args.output_dir),
                model_size=args.model,
                language=args.language,
                chunk_max_chars=args.chunk_max_chars,
                chunk_overlap_segments=args.chunk_overlap_segments,
            )
        )
        metadata = result["metadata"]
        manifest = result["manifest"]

        print("\n" + "=" * 60)
        print("SUCCESS")
        print(f"   Preview:    {metadata['preview_path']}")
        print(f"   Text:       {metadata['text_path']}")
        print(f"   Manifest:   {metadata['manifest_path']}")
        print(f"   Transcript: {metadata['transcript_path']}")
        print(f"   Chunks:     {metadata['chunk_path']}")
        print(f"   Language:   {manifest['language_detected']}")
        print(f"   Segments:   {manifest['counts']['segments']}")
        print(f"   Chunk count:{manifest['counts']['chunks']}")
        print("=" * 60)
    except VideoRagError as exc:
        print(f"\nPIPELINE FAILED: {exc}")
        raise SystemExit(1)
    except Exception as exc:
        print(f"\nPIPELINE FAILED: Unexpected error: {exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
