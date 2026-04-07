# Contributing

Thanks for your interest in `Tiktok-rag`.

This project is still early, so the most useful contributions are clarity, reproducibility, and sharp feedback about real workflows.

## Local setup

```bash
git clone https://github.com/Jia-Ethan/Tiktok-rag.git
cd Tiktok-rag
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

You also need `ffmpeg` installed on your system.

## Run the pipeline

```bash
python3 scripts/pipeline.py \
  --input /path/to/video.mp4 \
  --output-dir ./data
```

## What to open

- Use GitHub Discussions for roadmap ideas, product direction, and workflow feedback.
- Use GitHub Issues for concrete bugs or scoped feature requests.

## Contribution expectations

- Keep changes narrow and easy to review.
- Prefer improving reliability and clarity over adding half-finished features.
- If you change public behavior, update README or docs in the same PR.
