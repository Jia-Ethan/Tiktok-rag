#!/usr/bin/env python3
"""Local Gradio app for video-rag."""
import os
import sys
from pathlib import Path

try:
    import huggingface_hub

    if not hasattr(huggingface_hub, "HfFolder"):
        class _CompatHfFolder:
            @staticmethod
            def get_token():
                return huggingface_hub.get_token()

            @staticmethod
            def save_token(token: str) -> None:
                token_path = Path.home() / ".cache" / "huggingface" / "token"
                token_path.parent.mkdir(parents=True, exist_ok=True)
                token_path.write_text(token, encoding="utf-8")

            @staticmethod
            def delete_token() -> None:
                token_path = Path.home() / ".cache" / "huggingface" / "token"
                if token_path.exists():
                    token_path.unlink()

        huggingface_hub.HfFolder = _CompatHfFolder
except Exception:
    pass

try:
    import gradio as gr
except ImportError as exc:
    print(
        "ERROR: Missing dependency: gradio is not installed.\n"
        "Next step: activate your virtual environment and run `pip install -r requirements.txt`."
    )
    raise SystemExit(1) from exc


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.pipeline import (  # noqa: E402
    COMMON_LANGUAGE_CHOICES,
    DEFAULT_CHUNK_MAX_CHARS,
    DEFAULT_CHUNK_OVERLAP_SEGMENTS,
    DEFAULT_LANGUAGE,
    DEFAULT_WHISPER_MODEL,
    PipelineConfig,
    SUPPORTED_MODELS,
    VideoRagError,
    build_chunk_preview_markdown,
    format_seconds,
    run_pipeline,
)


DEFAULT_OUTPUT_DIR = ROOT / "data"
DEFAULT_HOST = os.getenv("VIDEO_RAG_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.getenv("VIDEO_RAG_PORT", "7860"))


def build_status_markdown(result: dict) -> str:
    metadata = result["metadata"]
    manifest = result["manifest"]
    counts = manifest["counts"]
    return "\n".join(
        [
            "## Processing complete",
            "",
            f"- Title: `{metadata['title']}`",
            f"- Language detected: `{manifest['language_detected']}`",
            f"- Duration: `{format_seconds(manifest['duration_seconds'])}`",
            f"- Transcript segments: `{counts['segments']}`",
            f"- Chunks: `{counts['chunks']}`",
            "",
            "### Open these files first",
            "",
            f"- `{Path(metadata['preview_path']).name}`: the easiest guided summary for first review",
            f"- `{Path(metadata['text_path']).name}`: plain text you can read, copy, or paste into notes",
            f"- `{Path(metadata['transcript_path']).name}`: raw timestamped transcript JSON",
            f"- `{Path(metadata['chunk_path']).name}`: chunk-ready JSON for later indexing or retrieval",
            f"- `{Path(metadata['meta_path']).name}`: metadata that links all generated files together",
            f"- `{Path(metadata['manifest_path']).name}`: one-file summary for UIs, scripts, and automation",
        ]
    )


def build_download_list(result: dict) -> list[str]:
    metadata = result["metadata"]
    return [
        metadata["text_path"],
        metadata["preview_path"],
        metadata["transcript_path"],
        metadata["chunk_path"],
        metadata["meta_path"],
        metadata["manifest_path"],
    ]


def process_video_for_ui(
    video_file: str,
    model_size: str,
    language: str,
    chunk_max_chars: int,
    chunk_overlap_segments: int,
    progress=gr.Progress(),
):
    if not video_file:
        raise gr.Error("请先选择一个本地视频文件。")

    logs: list[str] = []

    def on_log(message: str) -> None:
        logs.append(message)

    def on_progress(current_step: int, total_steps: int, message: str) -> None:
        ratio = 0 if total_steps == 0 else current_step / total_steps
        progress(ratio, desc=message)

    try:
        result = run_pipeline(
            PipelineConfig(
                input_path=Path(video_file),
                output_dir=DEFAULT_OUTPUT_DIR,
                model_size=model_size,
                language=language or DEFAULT_LANGUAGE,
                chunk_max_chars=int(chunk_max_chars),
                chunk_overlap_segments=int(chunk_overlap_segments),
            ),
            log_callback=on_log,
            progress_callback=on_progress,
            echo_logs=False,
        )
    except VideoRagError as exc:
        error_markdown = "\n".join(
            [
                "## Processing failed",
                "",
                str(exc),
            ]
        )
        return error_markdown, "\n".join(logs), "", "", "", []
    except Exception as exc:
        error_markdown = "\n".join(
            [
                "## Processing failed",
                "",
                f"Unexpected error: {exc}",
            ]
        )
        return error_markdown, "\n".join(logs), "", "", "", []

    return (
        build_status_markdown(result),
        "\n".join(logs),
        result["transcript_text"],
        build_chunk_preview_markdown(result["chunks"], max_chunks=20),
        result["preview_markdown"],
        build_download_list(result),
    )


with gr.Blocks(title="video-rag", theme=gr.themes.Soft()) as demo:
    gr.Markdown(
        """
        # video-rag

        把你已经下载到本地的视频，转成可直接阅读的文字结果和可下载的结构化文件。

        适合第一次试用的路径很简单：选一个本地视频文件，点开始处理，然后先看 `preview.md` 或 `text.txt`。
        """
    )

    with gr.Row():
        with gr.Column(scale=1):
            video_file = gr.File(
                label="本地视频文件",
                type="filepath",
                file_types=[".mp4", ".mov", ".mkv", ".m4v", ".webm"],
            )
            model_size = gr.Dropdown(
                choices=SUPPORTED_MODELS,
                value=DEFAULT_WHISPER_MODEL,
                label="Whisper 模型",
                info="默认 base。机器性能一般时先别急着用大模型。",
            )
            language = gr.Dropdown(
                choices=COMMON_LANGUAGE_CHOICES,
                value=DEFAULT_LANGUAGE,
                allow_custom_value=True,
                label="语言",
                info="默认 auto。你也可以手动指定 zh、en 等语言代码。",
            )
            with gr.Accordion("高级设置", open=False):
                chunk_max_chars = gr.Slider(
                    minimum=300,
                    maximum=2000,
                    value=DEFAULT_CHUNK_MAX_CHARS,
                    step=50,
                    label="Chunk 最大字符数",
                )
                chunk_overlap_segments = gr.Slider(
                    minimum=0,
                    maximum=3,
                    value=DEFAULT_CHUNK_OVERLAP_SEGMENTS,
                    step=1,
                    label="Chunk 重叠 segment 数",
                )

            run_button = gr.Button("开始处理", variant="primary")
            clear_button = gr.Button("清空结果")

        with gr.Column(scale=1):
            status_markdown = gr.Markdown(
                "## 等待开始\n\n处理完成后，这里会告诉你应该先打开哪个文件。"
            )
            log_output = gr.Textbox(
                label="处理日志",
                lines=14,
                max_lines=18,
                autoscroll=True,
                show_copy_button=True,
            )

    with gr.Tab("可读 Transcript"):
        transcript_text = gr.Textbox(
            label="整段可读文本",
            lines=18,
            max_lines=24,
            show_copy_button=True,
        )

    with gr.Tab("Chunk 预览"):
        chunk_preview = gr.Markdown("处理完成后，这里会显示 chunk 预览。")

    with gr.Tab("结果页预览"):
        preview_markdown = gr.Markdown("处理完成后，这里会显示 `preview.md` 的内容。")

    with gr.Tab("文件下载"):
        gr.Markdown(
            """
            下载区会提供普通用户最常用的 `txt / md / json` 文件。

            - `txt`：最适合直接阅读、复制、做笔记
            - `md`：最适合第一次整体查看结果
            - `json`：更适合开发者或后续自动化处理
            """
        )
        download_files = gr.File(label="下载产物", file_count="multiple")

    run_button.click(
        fn=process_video_for_ui,
        inputs=[
            video_file,
            model_size,
            language,
            chunk_max_chars,
            chunk_overlap_segments,
        ],
        outputs=[
            status_markdown,
            log_output,
            transcript_text,
            chunk_preview,
            preview_markdown,
            download_files,
        ],
        show_progress="full",
        show_api=False,
    )

    clear_button.click(
        fn=lambda: (
            "## 等待开始\n\n处理完成后，这里会告诉你应该先打开哪个文件。",
            "",
            "",
            "处理完成后，这里会显示 chunk 预览。",
            "处理完成后，这里会显示 `preview.md` 的内容。",
            [],
        ),
        outputs=[
            status_markdown,
            log_output,
            transcript_text,
            chunk_preview,
            preview_markdown,
            download_files,
        ],
        show_api=False,
    )


if __name__ == "__main__":
    demo.launch(
        server_name=DEFAULT_HOST,
        server_port=DEFAULT_PORT,
        show_api=False,
    )
