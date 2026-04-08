# video-rag

**A local-first ingestion foundation that turns downloaded videos into timestamped text assets and chunk-ready artifacts for downstream RAG workflows.**

一个本地优先的 ingestion foundation，把已下载视频转成带时间戳的文本资产，供后续 RAG 工作流继续使用。

当前版本的核心价值不是“已经做完 Video RAG”，而是先把视频进入 RAG 工作流前最容易失真、最难复用的第一步做成一个干净、公开、可检查的基础层；并进一步给出面向下游知识处理的 chunk-ready 中间层资产。

![CLI demo](docs/assets/cli-demo.svg)

## What this repo is today

`video-rag` is a single-video ingestion and transcription foundation for developers who already have downloaded video files and want stable transcript, metadata, and chunk-ready artifacts for downstream processing.

它现在是一个单视频 ingestion / transcription foundation。输入是已下载到本地的视频文件，输出是后续可以继续加工的 transcript、metadata 和 chunk-ready artifacts。

## What it is not yet

It is **not** a full Video RAG product yet. It does not support URL input, vector storage, retrieval, Web UI, or batch ingestion in the current release.

它**还不是**一个完整的 Video RAG 产品。当前版本不支持 URL 输入，也没有向量库、retrieval、Web UI 或批量处理。

## What comes next

The next step is to build a minimal retrieval-ready loop on top of the new chunk artifact contract.

下一步不是盲目加功能，而是基于现在已经落地的 chunk-ready artifact，继续推进最小可检索闭环。

## Who this is for

- Local-first AI engineers and indie developers
- Builders who already have downloaded videos and want text assets they can inspect, cite, chunk, index, summarize, or feed into prompts
- People building early-stage video knowledge workflows before retrieval and UI layers exist

## Who this is not for yet

- Users who want to paste a URL and get a full workflow immediately
- Users who expect built-in question answering or searchable retrieval today
- Non-technical users who need a polished product UI
- Teams that need batch ingestion, collaboration, or operational workflows right away

## What it does

- Accepts downloaded local video files such as `.mp4`, `.mov`, and `.mkv`
- Extracts 16kHz mono WAV audio with `ffmpeg`
- Transcribes speech with `faster-whisper`
- Writes transcript JSON, metadata JSON, and chunk-ready JSON for downstream processing

## Demo output

The current public demo takes one downloaded local video file and produces four artifacts:

- `data/audio/<job_id>.wav`
- `data/transcripts/<job_id>.json`
- `data/meta/<job_id>.meta.json`
- `data/chunks/<job_id>.chunks.json`

These are not just debug files. They are reusable intermediate artifacts for later retrieval, summary, and knowledge workflows.

See the public sample output:

- [docs/public-sample-output.md](docs/public-sample-output.md)
- [docs/chunk-artifact-spec.md](docs/chunk-artifact-spec.md)

## Why this output is useful

- The transcript turns video content into inspectable and reviewable text
- Metadata preserves source, file relationship, and processing context for traceability
- The chunk artifact turns raw transcript segments into stable downstream knowledge units
- Timestamps make later citation, jump-back review, and source alignment more reliable
- These artifacts are the natural input layer for indexing, retrieval, summary generation, and prompt context construction

## Why not just use a quick Whisper script?

- `video-rag` is local-first and built around downloaded videos as a stable ingestion boundary
- It produces structured artifacts, not just one-off text output
- Transcript + metadata + chunk artifacts form a better system starting point than a disposable script result
- The repo is public, inspectable, and easier to extend into a larger workflow than an ad hoc local script

## Use cases

- Turning downloaded videos into text assets for later retrieval work
- Preparing transcript material before summary, outline, or note generation
- Building a video knowledge archive with source traceability
- Creating prompt-ready context from videos without manually replaying the source
- Using chunk-ready artifacts as the input layer for a custom embedding or retrieval stack

## Quickstart

### Requirements

- Python 3.9+
- `ffmpeg`

Install `ffmpeg`:

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg
```

### Setup

```bash
git clone https://github.com/Jia-Ethan/video-rag.git
cd video-rag
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Run

```bash
python3 scripts/pipeline.py \
  --input /path/to/downloaded-video.mp4 \
  --output-dir ./data
```

Optional model selection:

```bash
python3 scripts/pipeline.py \
  --input /path/to/downloaded-video.mp4 \
  --output-dir ./data \
  --model small
```

## Supported input

- Downloaded local video files only
- Recommended formats: `.mp4`, `.mov`, `.mkv`

## Output artifacts

### `data/audio/<job_id>.wav`

Normalized 16kHz mono WAV audio extracted from the source video.

### `data/transcripts/<job_id>.json`

Timestamped transcript output from `faster-whisper`, including segment timing and optional word-level timing when available.

### `data/meta/<job_id>.meta.json`

Processing metadata that links the original input file, generated audio, transcript path, segment count, and model choice.

### `data/chunks/<job_id>.chunks.json`

A chunk-ready intermediate artifact that groups transcript segments into stable knowledge units with text, time range, source traceability, and neighboring chunk references.

This is the main file to build against if you want to add embeddings, retrieval, summaries, or prompt assembly on top of the current pipeline.

## Known limitations

- URL inputs are not supported in this release
- No vector store, retrieval UI, or Web app yet
- No batch ingestion yet
- Long-video behavior has not been systematically characterized
- Multi-language, noisy audio, and multi-speaker handling are not yet systematically validated
- The current chunking strategy is structural and conservative; it is not semantic chunking

## Evaluation status

Current validation is limited to smoke tests and sample-level verification.

- Basic local ingestion, transcription, and chunk artifact generation are working
- Output structure is stable enough to build against for downstream experimentation
- Systematic benchmarking for long videos, multilingual audio, noisy inputs, and performance has **not** been completed yet

## Roadmap

### Phase 1 — Single video to usable text asset

Users get one downloaded video turned into transcript + metadata artifacts they can inspect and reuse. This is the foundation that makes later retrieval work possible without redoing ingestion.

### Phase 2 — Single video to minimal retrieval-ready loop

Users now get chunk-ready output as the first retrieval-ready precursor, and the next move is a minimal retrieval-ready layer on top of it. This is the critical step that turns the repo from ingestion foundation into a first real closed loop.

### Phase 3 — Multi-video retrieval and organization

Users get a path from one processed video to a searchable multi-video corpus. This matters because knowledge workflows become more valuable once artifacts can be grouped and queried across sources.

### Phase 4 — Better reliability for longer and noisier videos

Users get stronger output quality and more trustworthy behavior on longer, messier real-world inputs. This matters because practical adoption depends on robustness, not just happy-path demos.

## What feedback is most helpful

The most useful feedback right now is not “looks cool,” but real workflow context:

- Where your videos come from
- Typical video duration
- Main language or language mix
- Whether chunk-ready output already reduces your integration work
- Whether your next step is retrieval, summary, knowledge organization, or prompt context construction
- What would make this repo useful enough to stay in your workflow

If you want a quick guide for giving useful feedback, see:

- [docs/feedback-guide.md](docs/feedback-guide.md)
- [docs/chunk-artifact-spec.md](docs/chunk-artifact-spec.md)

## Feedback

- Roadmap and workflow feedback: [GitHub Discussions](https://github.com/Jia-Ethan/video-rag/discussions)
- Reproducible bugs or scoped feature requests: [GitHub Issues](https://github.com/Jia-Ethan/video-rag/issues)
- Direct contact: `ethan_pier@icloud.com`

## Project structure

```text
video-rag/
├── app/                     # Reserved for future UI work
├── docs/
│   ├── assets/
│   ├── chunk-artifact-spec.md
│   ├── discussions/
│   ├── feedback-guide.md
│   └── public-sample-output.md
├── scripts/
│   └── pipeline.py
├── data/                    # Runtime output (gitignored)
│   ├── audio/
│   ├── chunks/
│   ├── meta/
│   └── transcripts/
├── .github/
│   └── ISSUE_TEMPLATE/
├── CONTRIBUTING.md
├── LICENSE
└── requirements.txt
```

## License

[MIT](LICENSE)
