#!/usr/bin/env python3
"""
抖音/本地视频知识库 MVP — 核心处理管线
最小主链路：mp4 → 音频抽出 → 语音转写 → 标准化输出

依赖：
  pip install faster-whisper --target ~/PythonPackages
  # 或：pip install faster-whisper

使用：
  # 方式A：本地 mp4
  python3 pipeline.py --input /path/to/video.mp4 --output-dir ./data

  # 方式B：抖音分享链接（需要 cookies，或降级到本地路线）
  python3 pipeline.py --input "https://v.douyin.com/xxxxx" --output-dir ./data
"""
import os
import sys
import json
import hashlib
import argparse
import subprocess
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

# faster-whisper 路径
PYTHONPACKAGES = os.path.expanduser("~/PythonPackages")
if os.path.exists(PYTHONPACKAGES):
    sys.path.insert(0, PYTHONPACKAGES)

try:
    from faster_whisper import WhisperModel
except ImportError:
    print("ERROR: faster-whisper not found. Run: pip install faster-whisper --target ~/PythonPackages")
    sys.exit(1)


# ─── 配置 ────────────────────────────────────────────────────────────────────

CST = timezone(timedelta(hours=8))  # 北京时间

DEFAULT_WHISPER_MODEL = "base"      # tiny / base / small / medium / large-v3
DEFAULT_COMPUTE_TYPE = "auto"      # auto / float16 / int8 / float32
FFMPEG_BIN = "ffmpeg"


# ─── 工具函数 ────────────────────────────────────────────────────────────────

def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def run_cmd(cmd: list[str], check: bool = True, capture: bool = True) -> str:
    """运行 shell 命令，返回 stdout"""
    print(f"  CMD: {' '.join(str(x) for x in cmd)}")
    result = subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        check=False
    )
    if result.returncode != 0 and check:
        print(f"  ERROR: {result.stderr[:500]}")
        raise RuntimeError(f"Command failed: {' '.join(str(x) for x in cmd)}\n{result.stderr[:300]}")
    return result.stdout if capture else ""


def extract_video_id(url: str) -> Optional[str]:
    """从抖音 URL 中提取 video ID（如果有）"""
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
    尝试用 yt-dlp 下载抖音视频。
    返回 Path 或 None（失败时降级）。
    注意：抖音需要登录 cookies，否则会失败。
    """
    print(f"[Douyin] Attempting to download: {url}")
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
        run_cmd(cmd, check=True)
        # yt-dlp 可能生成 .mp4 或其他格式，找最新生成的文件
        candidate = output_path.with_suffix(".mp4")
        if candidate.exists():
            return candidate
        # 查找 yt-dlp 生成的任何视频文件
        for f in output_path.parent.glob(f"{output_path.stem}.*"):
            if f.suffix.lower() in [".mp4", ".mkv", ".webm", ".flv"]:
                return f
    except Exception as e:
        print(f"  [Douyin] Download failed: {e}")
        print("  [Douyin] Falling back to local mp4 route.")
    return None


def extract_audio(video_path: Path, audio_path: Path) -> None:
    """用 ffmpeg 抽出音频（wav, 16kHz, mono）"""
    cmd = [
        FFMPEG_BIN, "-y",
        "-i", str(video_path),
        "-vn",                       # 不要视频
        "-acodec", "pcm_s16le",     # WAV PCM
        "-ar", "16000",              # 16kHz
        "-ac", "1",                  # 单声道
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
    用 faster-whisper 转写音频，输出带时间戳的 JSON。
    返回 transcript 数据结构。
    """
    print(f"[Whisper] Loading model '{model_size}' (compute={compute_type})...")
    model = WhisperModel(
        model_size,
        device="auto",     # cuda / cpu
        compute_type=compute_type,
    )

    print(f"[Whisper] Transcribing {audio_path}...")
    segments, info = model.transcribe(
        str(audio_path),
        language="zh",    # 强制中文
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
        # 词级时间戳（如果有）
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

    # 写 JSON
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(transcript_data, f, ensure_ascii=False, indent=2)

    print(f"[Whisper] Saved: {output_json}  ({len(transcript_data['segments'])} segments)")
    return transcript_data


# ─── 主流程 ─────────────────────────────────────────────────────────────────

def process_local_mp4(mp4_path: Path, output_dir: Path,
                       model_size: str = DEFAULT_WHISPER_MODEL) -> dict:
    """
    完整流程：本地 mp4 → 音频抽出 → 转写 → metadata JSON
    返回 metadata dict。
    """
    print(f"\n=== Processing local MP4: {mp4_path} ===")
    ensure_dir(output_dir)

    audio_dir = output_dir / "audio"
    transcript_dir = output_dir / "transcripts"
    meta_dir = output_dir / "meta"
    ensure_dir(audio_dir)
    ensure_dir(transcript_dir)
    ensure_dir(meta_dir)

    # 生成 job_id（基于文件名 + 时间戳）
    stem = mp4_path.stem
    job_id = hashlib.md5(f"{stem}{os.path.getsize(mp4_path)}{datetime.now(CST).isoformat()}".encode()).hexdigest()[:12]
    audio_path = audio_dir / f"{job_id}.wav"
    transcript_path = transcript_dir / f"{job_id}.json"

    # Step 1: 抽出音频
    print(f"\n[Step 1/3] Extracting audio → {audio_path}")
    extract_audio(mp4_path, audio_path)

    # Step 2: 转写
    print(f"\n[Step 2/3] Transcribing → {transcript_path}")
    transcript_data = transcribe(audio_path, transcript_path, model_size=model_size)

    # Step 3: 生成 metadata
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

    print(f"[Done] metadata: {meta_path}")
    return metadata


def process_douyin_share(url: str, output_dir: Path,
                           model_size: str = DEFAULT_WHISPER_MODEL) -> dict:
    """
    抖音分享链接流程：下载 → 本地处理
    如果下载失败，降级到本地路线并报告。
    """
    print(f"\n=== Processing Douyin share URL: {url} ===")

    video_id = extract_video_id(url)
    print(f"[Douyin] Extracted video_id: {video_id}")

    # 临时下载目录
    raw_dir = output_dir / "raw"
    ensure_dir(raw_dir)

    tmp_video = raw_dir / f"douyin_{video_id or 'tmp'}"
    downloaded = download_douyin(url, tmp_video)

    if downloaded is None:
        print("\n⚠️  Douyin download failed (需要登录 cookies 或受地区限制）")
        print("   请提供本地 mp4 文件继续测试，或配置 yt-dlp cookies。")
        raise RuntimeError(
            "Douyin download blocked. Please use local mp4 instead:\n"
            f"  python3 {__file__} --input /path/to/video.mp4 --output-dir ./data"
        )

    # 用下载的文件走标准流程
    metadata = process_local_mp4(downloaded, output_dir, model_size=model_size)
    # 更新 metadata 中的抖音来源字段
    metadata["source_type"] = "douyin_share"
    metadata["platform"] = "douyin"
    metadata["video_id"] = video_id
    metadata["input_url_or_path"] = url

    # 回写更新后的 metadata
    meta_path = Path(metadata["transcript_path"]).parent.parent / "meta" / Path(metadata["transcript_path"]).stem + ".meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    return metadata


# ─── CLI 入口 ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="抖音/本地视频知识库 MVP — 核心管线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--input", "-i", required=True,
                        help="本地 mp4 路径，或抖音分享链接")
    parser.add_argument("--output-dir", "-o", default="./data",
                        help="输出根目录（默认 ./data）")
    parser.add_argument("--model", "-m", default=DEFAULT_WHISPER_MODEL,
                        choices=["tiny", "base", "small", "medium", "large-v3"],
                        help=f"Whisper 模型（默认 {DEFAULT_WHISPER_MODEL}）")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()

    input_val = args.input.strip()

    # 判断输入类型
    is_url = input_val.startswith("http://") or input_val.startswith("https://")
    is_douyin = "douyin.com" in input_val or "v.douyin.com" in input_val

    try:
        if is_douyin or is_url:
            metadata = process_douyin_share(input_val, output_dir, model_size=args.model)
        else:
            mp4_path = Path(input_val).expanduser().resolve()
            if not mp4_path.exists():
                print(f"ERROR: File not found: {mp4_path}")
                sys.exit(1)
            metadata = process_local_mp4(mp4_path, output_dir, model_size=args.model)

        audio_file = Path(metadata["audio_path"]).name
        meta_file = Path(metadata["transcript_path"]).stem.replace(".json", "") + ".meta.json"
        print("\n" + "=" * 60)
        print("✅ PIPELINE COMPLETE")
        print(f"   Meta:     {output_dir}/meta/{meta_file}")
        print(f"   Audio:    {output_dir}/audio/{audio_file}")
        print(f"   Transcript: {metadata['transcript_path'].split('/')[-1]}")
        print(f"   Segments: {metadata['transcript_segments']}")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ PIPELINE FAILED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
