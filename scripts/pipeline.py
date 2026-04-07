#!/usr/bin/env python3
"""
Tiktok-rag pipeline.

Current public support:
  - local video files: stable
  - Douyin/TikTok URL ingestion: experimental placeholder only

Quickstart:
  python3 scripts/pipeline.py --input /path/to/video.mp4 --output-dir ./data
"""
import os
import json
import hashlib
import argparse
import subprocess
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

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


def extract_video_id(url: str) -> Optional[str]:
    """Extract a best-effort video identifier from a Douyin/TikTok URL."""
    patterns = [
        r'/video/(\d+)',
        r'v\.douyin\.com/([A-Za-z0-9]+)',
        r'(\d{19,})',
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None


def download_douyin(url: str, output_path: Path) -> Optional[Path]:
    """
    Best-effort Douyin/TikTok download via yt-dlp.
    Returns a local Path on success, or None on failure.
    """
    print(f"[URL Ingestion] Attempting download: {url}")
    cmd = [
        "yt-dlp",
        "--no-warnings",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--output", str(output_path.with_suffix(".%(ext)s")),
        "--write-info-json",
        "--no-playlist",
        url,
    ]
    try:
        run_cmd(cmd, check=True, show_error=False)
        candidate = output_path.with_suffix(".mp4")
        if candidate.exists():
            return candidate
        for f in output_path.parent.glob(f"{output_path.stem}.*"):
            if f.suffix.lower() in [".mp4", ".mkv", ".webm", ".flv"]:
                return f
    except Exception as e:
        print("  [URL Ingestion] Download failed in the current public setup.")
        print(f"  [URL Ingestion] Internal detail: {type(e).__name__}")
    return None


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


# ─── 主流程 ─────────────────────────────────────────────────────────────────

def process_local_mp4(mp4_path: Path, output_dir: Path,
                       model_size: str = DEFAULT_WHISPER_MODEL) -> dict:
    """Process a local video file end to end and return metadata."""
    print(f"\n=== Processing local video: {mp4_path} ===")
    ensure_dir(output_dir)

    audio_dir = output_dir / "audio"
    transcript_dir = output_dir / "transcripts"
    meta_dir = output_dir / "meta"
    ensure_dir(audio_dir)
    ensure_dir(transcript_dir)
    ensure_dir(meta_dir)

    stem = mp4_path.stem
    job_id = hashlib.md5(f"{stem}{os.path.getsize(mp4_path)}{datetime.now(CST).isoformat()}".encode()).hexdigest()[:12]
    audio_path = audio_dir / f"{job_id}.wav"
    transcript_path = transcript_dir / f"{job_id}.json"

    print(f"\n[Step 1/3] Extracting audio → {audio_path}")
    extract_audio(mp4_path, audio_path)

    print(f"\n[Step 2/3] Transcribing → {transcript_path}")
    transcript_data = transcribe(audio_path, transcript_path, model_size=model_size)

    print(f"\n[Step 3/3] Writing metadata")
    metadata = {
        "source_type": "local_mp4",
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

    print(f"[Done] Metadata saved: {meta_path}")
    return metadata


def process_douyin_share(url: str, output_dir: Path,
                           model_size: str = DEFAULT_WHISPER_MODEL) -> dict:
    """Best-effort experimental handling for Douyin/TikTok share URLs."""
    print(f"\n=== Processing experimental URL input: {url} ===")

    video_id = extract_video_id(url)
    print(f"[URL Ingestion] Extracted video_id: {video_id}")

    raw_dir = output_dir / "raw"
    ensure_dir(raw_dir)

    tmp_video = raw_dir / f"douyin_{video_id or 'tmp'}"
    downloaded = download_douyin(url, tmp_video)

    if downloaded is None:
        raise RuntimeError(
            "Douyin/TikTok URL ingestion is experimental and not publicly supported yet.\n"
            "Please use a local video file instead:\n"
            f"  python3 {__file__} --input /path/to/video.mp4 --output-dir ./data"
        )

    metadata = process_local_mp4(downloaded, output_dir, model_size=model_size)
    metadata["source_type"] = "douyin_share"
    metadata["platform"] = "douyin"
    metadata["video_id"] = video_id
    metadata["input_url_or_path"] = url

    meta_path = Path(metadata["transcript_path"]).parent.parent / "meta" / f"{Path(metadata['transcript_path']).stem}.meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"[Done] Experimental URL metadata updated: {meta_path}")
    return metadata


# ─── CLI 入口 ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Tiktok-rag local-first short-video pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--input", "-i", required=True,
                        help="Local video path, or an experimental Douyin/TikTok URL")
    parser.add_argument("--output-dir", "-o", default="./data",
                        help="Output root directory (default: ./data)")
    parser.add_argument("--model", "-m", default=DEFAULT_WHISPER_MODEL,
                        choices=["tiny", "base", "small", "medium", "large-v3"],
                        help=f"Whisper model (default: {DEFAULT_WHISPER_MODEL})")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()

    input_val = args.input.strip()

    is_url = input_val.startswith("http://") or input_val.startswith("https://")
    is_douyin = "douyin.com" in input_val or "v.douyin.com" in input_val
    is_tiktok = "tiktok.com" in input_val or "vt.tiktok.com" in input_val

    try:
        if is_douyin or is_tiktok:
            metadata = process_douyin_share(input_val, output_dir, model_size=args.model)
        elif is_url:
            raise RuntimeError(
                "Unsupported URL source. This release only supports local files publicly, "
                "with experimental Douyin/TikTok placeholders."
            )
        else:
            mp4_path = Path(input_val).expanduser().resolve()
            if not mp4_path.exists():
                print(f"ERROR: File not found: {mp4_path}")
                raise SystemExit(1)
            metadata = process_local_mp4(mp4_path, output_dir, model_size=args.model)

        audio_file = Path(metadata["audio_path"]).name
        meta_file = f"{Path(metadata['transcript_path']).stem}.meta.json"
        print("\n" + "=" * 60)
        print("SUCCESS")
        print(f"   Meta:       {output_dir}/meta/{meta_file}")
        print(f"   Audio:      {output_dir}/audio/{audio_file}")
        print(f"   Transcript: {Path(metadata['transcript_path']).name}")
        print(f"   Segments:   {metadata['transcript_segments']}")
        print("=" * 60)

    except Exception as e:
        print(f"\nPIPELINE FAILED: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
