#!/usr/bin/env python3
"""
video-rag pipeline.

This release supports downloaded local video files only.
It produces transcript, metadata, and chunk-ready artifacts.

Quickstart:
  python3 scripts/pipeline.py --input /path/to/downloaded-video.mp4 --output-dir ./data
"""
import os
import json
import hashlib
import argparse
import subprocess
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    from faster_whisper import WhisperModel
except ImportError:
    print("ERROR: faster-whisper is not installed. Activate your venv and run: pip install -r requirements.txt")
    raise SystemExit(1)


# ─── 配置 ────────────────────────────────────────────────────────────────────

CST = timezone(timedelta(hours=8))  # 北京时间

DEFAULT_WHISPER_MODEL = "base"      # tiny / base / small / medium / large-v3
DEFAULT_COMPUTE_TYPE = "auto"      # auto / float16 / int8 / float32
FFMPEG_BIN = "ffmpeg"
DEFAULT_CHUNK_MAX_CHARS = 900
DEFAULT_CHUNK_OVERLAP_SEGMENTS = 1
CHUNKING_VERSION = "1.0"
CHUNKING_STRATEGY = "segment_grouped_char_limit_v1"


# ─── 工具函数 ────────────────────────────────────────────────────────────────

def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def run_cmd(cmd: list[str], check: bool = True, capture: bool = True, show_error: bool = True) -> str:
    """Run a shell command and return stdout."""
    print(f"  CMD: {' '.join(str(x) for x in cmd)}")
    result = subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        check=False
    )
    if result.returncode != 0 and check:
        if show_error and result.stderr:
            print(f"  ERROR: {result.stderr[:500]}")
        raise RuntimeError(f"Command failed: {' '.join(str(x) for x in cmd)}\n{result.stderr[:300]}")
    return result.stdout if capture else ""


def is_cjk_char(char: str) -> bool:
    return "\u4e00" <= char <= "\u9fff"


def merge_segment_texts(texts: list[str]) -> str:
    """Join transcript segments into a readable chunk text."""
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
    """A lightweight token estimate for documentation and downstream heuristics."""
    cjk_chars = sum(1 for char in text if is_cjk_char(char))
    other_chars = sum(1 for char in text if not char.isspace() and not is_cjk_char(char))
    return max(1, math.ceil(cjk_chars / 1.5) + math.ceil(other_chars / 4))


def extract_audio(video_path: Path, audio_path: Path) -> None:
    """Extract mono 16kHz WAV audio with ffmpeg."""
    cmd = [
        FFMPEG_BIN, "-y",
        "-i", str(video_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        "-loglevel", "error",
        str(audio_path),
    ]
    run_cmd(cmd, check=True)
    if not audio_path.exists():
        raise RuntimeError(f"Audio extraction failed: {audio_path} not created")


def transcribe(audio_path: Path, output_json: Path,
               model_size: str = DEFAULT_WHISPER_MODEL,
               compute_type: str = DEFAULT_COMPUTE_TYPE) -> dict:
    """
    Transcribe audio with faster-whisper and write timestamped JSON output.
    """
    print(f"[Whisper] Loading model '{model_size}' (compute={compute_type})...")
    model = WhisperModel(
        model_size,
        device="auto",
        compute_type=compute_type,
    )

    print(f"[Whisper] Transcribing {audio_path}...")
    segments, info = model.transcribe(
        str(audio_path),
        language="zh",
        word_timestamps=True,
        initial_prompt="以下是普通话语音，内容为中文。",
    )

    print(f"[Whisper] Detected language: {info.language}  "
          f"({info.language_probability:.0%}), "
          f"duration: {info.duration:.1f}s")

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
                    "word": w.word,
                    "start": round(w.start, 2),
                    "end": round(w.end, 2),
                    "probability": round(w.probability, 3),
                }
                for w in seg.words
            ]
        transcript_data["segments"].append(seg_data)

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(transcript_data, f, ensure_ascii=False, indent=2)

    print(f"[Whisper] Saved: {output_json}  ({len(transcript_data['segments'])} segments)")
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
    """Build a chunk-ready artifact from transcript segments."""
    segments = transcript_data.get("segments", [])
    chunks: list[dict] = []

    def make_chunk(segment_indexes: list[int], chunk_index: int) -> dict:
        chunk_segments = [segments[idx] for idx in segment_indexes]
        chunk_text = merge_segment_texts([segment["text"] for segment in chunk_segments])
        start = round(chunk_segments[0]["start"], 2)
        end = round(chunk_segments[-1]["end"], 2)
        return {
            "chunk_id": f"{metadata['job_id']}-chunk-{chunk_index:03d}",
            "index": chunk_index,
            "start": start,
            "end": end,
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


# ─── 主流程 ─────────────────────────────────────────────────────────────────

def process_local_mp4(mp4_path: Path, output_dir: Path,
                       model_size: str = DEFAULT_WHISPER_MODEL,
                       chunk_max_chars: int = DEFAULT_CHUNK_MAX_CHARS,
                       chunk_overlap_segments: int = DEFAULT_CHUNK_OVERLAP_SEGMENTS) -> dict:
    """Process a local video file end to end and return metadata."""
    print(f"\n=== Processing local video: {mp4_path} ===")
    ensure_dir(output_dir)

    audio_dir = output_dir / "audio"
    chunks_dir = output_dir / "chunks"
    transcript_dir = output_dir / "transcripts"
    meta_dir = output_dir / "meta"
    ensure_dir(audio_dir)
    ensure_dir(chunks_dir)
    ensure_dir(transcript_dir)
    ensure_dir(meta_dir)

    stem = mp4_path.stem
    job_id = hashlib.md5(f"{stem}{os.path.getsize(mp4_path)}{datetime.now(CST).isoformat()}".encode()).hexdigest()[:12]
    audio_path = audio_dir / f"{job_id}.wav"
    transcript_path = transcript_dir / f"{job_id}.json"

    print(f"\n[Step 1/4] Extracting audio → {audio_path}")
    extract_audio(mp4_path, audio_path)

    print(f"\n[Step 2/4] Transcribing → {transcript_path}")
    transcript_data = transcribe(audio_path, transcript_path, model_size=model_size)

    print(f"\n[Step 3/4] Writing metadata")
    metadata = {
        "job_id": job_id,
        "source_type": "local_video",
        "platform": "local",
        "input_path": str(mp4_path.resolve()),
        "input_size_bytes": os.path.getsize(mp4_path),
        "video_id": None,
        "title": stem,
        "caption": None,
        "audio_path": str(audio_path.resolve()),
        "transcript_path": str(transcript_path.resolve()),
        "transcript_segments": len(transcript_data["segments"]),
        "transcript_duration_seconds": transcript_data.get("duration_seconds"),
        "whisper_model": transcript_data.get("model"),
        "created_at": datetime.now(CST).isoformat(),
    }

    meta_path = meta_dir / f"{job_id}.meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"\n[Step 4/4] Writing chunk-ready artifact")
    chunk_path = chunks_dir / f"{job_id}.chunks.json"
    chunk_artifact = build_chunk_artifact(
        transcript_data,
        metadata,
        transcript_path,
        meta_path,
        chunk_path,
        max_chars=chunk_max_chars,
        overlap_segments=chunk_overlap_segments,
    )
    metadata["chunk_path"] = str(chunk_path.resolve())
    metadata["chunk_count"] = chunk_artifact["chunk_count"]
    metadata["chunking_strategy"] = chunk_artifact["chunking_strategy"]
    metadata["chunking_version"] = chunk_artifact["chunking_version"]

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"[Done] Metadata saved: {meta_path}")
    return metadata


# ─── CLI 入口 ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="video-rag local video transcription pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--input", "-i", required=True,
                        help="Downloaded local video file path")
    parser.add_argument("--output-dir", "-o", default="./data",
                        help="Output root directory (default: ./data)")
    parser.add_argument("--model", "-m", default=DEFAULT_WHISPER_MODEL,
                        choices=["tiny", "base", "small", "medium", "large-v3"],
                        help=f"Whisper model (default: {DEFAULT_WHISPER_MODEL})")
    parser.add_argument("--chunk-max-chars", type=int, default=DEFAULT_CHUNK_MAX_CHARS,
                        help=f"Approximate character limit per chunk (default: {DEFAULT_CHUNK_MAX_CHARS})")
    parser.add_argument("--chunk-overlap-segments", type=int, default=DEFAULT_CHUNK_OVERLAP_SEGMENTS,
                        help=f"How many transcript segments to overlap between chunks (default: {DEFAULT_CHUNK_OVERLAP_SEGMENTS})")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()

    input_val = args.input.strip()

    try:
        if input_val.startswith("http://") or input_val.startswith("https://"):
            raise RuntimeError(
                "URL inputs are not supported in this release. "
                "Please use a downloaded local video file."
            )
        if args.chunk_max_chars < 1:
            raise RuntimeError("--chunk-max-chars must be a positive integer.")
        if args.chunk_overlap_segments < 0:
            raise RuntimeError("--chunk-overlap-segments must be zero or greater.")

        mp4_path = Path(input_val).expanduser().resolve()
        if not mp4_path.exists():
            print(f"ERROR: File not found: {mp4_path}")
            raise SystemExit(1)
        metadata = process_local_mp4(
            mp4_path,
            output_dir,
            model_size=args.model,
            chunk_max_chars=args.chunk_max_chars,
            chunk_overlap_segments=args.chunk_overlap_segments,
        )

        audio_file = Path(metadata["audio_path"]).name
        chunk_file = Path(metadata["chunk_path"]).name
        meta_file = f"{Path(metadata['transcript_path']).stem}.meta.json"
        print("\n" + "=" * 60)
        print("SUCCESS")
        print(f"   Meta:       {output_dir}/meta/{meta_file}")
        print(f"   Audio:      {output_dir}/audio/{audio_file}")
        print(f"   Transcript: {Path(metadata['transcript_path']).name}")
        print(f"   Chunks:     {chunk_file}")
        print(f"   Segments:   {metadata['transcript_segments']}")
        print(f"   Chunk count:{metadata['chunk_count']}")
        print("=" * 60)

    except Exception as e:
        print(f"\nPIPELINE FAILED: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
