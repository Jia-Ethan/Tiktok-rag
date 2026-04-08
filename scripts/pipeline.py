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
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional


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
        "audio_path": output_dir / "audio" / f"{job_id}.wav",
        "transcript_path": output_dir / "transcripts" / f"{job_id}.json",
        "meta_path": output_dir / "meta" / f"{job_id}.meta.json",
        "chunk_path": output_dir / "chunks" / f"{job_id}.chunks.json",
        "text_path": output_dir / "text" / f"{job_id}.txt",
        "preview_path": output_dir / "preview" / f"{job_id}.md",
        "manifest_path": output_dir / "manifests" / f"{job_id}.manifest.json",
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
        "",
        "## What each output file is for",
        "",
        f"- `{text_path.name}`: best for ordinary reading, quick copy, and note-taking",
        f"- `{preview_path.name}`: best for first review with chunk preview and output guide",
        f"- `{Path(metadata['transcript_path']).name}`: raw timestamped transcript JSON",
        f"- `{Path(metadata['chunk_path']).name}`: chunk-ready intermediate artifact for downstream indexing or retrieval",
        f"- `{Path(metadata['manifest_path']).name}`: one-file summary for apps and automation",
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
) -> dict:
    return {
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
        },
        "artifact_descriptions": {
            "text_txt": "Best for ordinary reading, copy, and note-taking.",
            "preview_markdown": "Best first file for a guided review of the run.",
            "transcript_json": "Raw timestamped transcript for developer-facing processing.",
            "chunks_json": "Chunk-ready intermediate artifact for downstream indexing or retrieval.",
            "metadata_json": "Processing metadata that links source and generated artifacts.",
            "manifest_json": "One-file summary for UIs, automation, and downstream integrations.",
        },
    }


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
    )
    write_json(paths["manifest_path"], manifest)
    write_json(paths["meta_path"], metadata)

    emit_log(f"[Done] Manifest saved: {paths['manifest_path']}", log_callback=log_callback, echo=echo_logs)
    emit_progress(total_steps, total_steps, "Completed", progress_callback=progress_callback)

    return {
        "job_id": job_id,
        "metadata": metadata,
        "transcript": transcript_data,
        "chunks": chunk_artifact,
        "manifest": manifest,
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
