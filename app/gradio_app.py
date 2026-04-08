#!/usr/bin/env python3
"""Local Gradio app for video-rag."""
import os
import sys
from pathlib import Path
from typing import Optional

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
    DEFAULT_QA_RETRIEVAL_LIMIT,
    DEFAULT_SEARCH_LIMIT,
    DEFAULT_WHISPER_MODEL,
    MAX_QA_RETRIEVAL_LIMIT,
    PipelineConfig,
    SUPPORTED_MODELS,
    VideoRagError,
    build_chunk_preview_markdown,
    contains_cjk,
    export_qa_result,
    export_search_results,
    export_video_summary,
    format_seconds,
    load_history_records,
    load_video_bundle,
    run_grounded_qa,
    run_pipeline,
    search_chunk_artifact,
)


DEFAULT_OUTPUT_DIR = ROOT / "data"
DEFAULT_HOST = os.getenv("VIDEO_RAG_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.getenv("VIDEO_RAG_PORT", "7860"))
DEFAULT_QA_BASE_URL = os.getenv("VIDEO_RAG_QA_BASE_URL", "")
DEFAULT_QA_MODEL = os.getenv("VIDEO_RAG_QA_MODEL", "")
DEFAULT_QA_API_KEY = os.getenv("VIDEO_RAG_QA_API_KEY", "")


def history_choice_label(record: dict) -> str:
    return (
        f"{record['source_title']} | {record['created_at'] or 'unknown time'} | "
        f"{record['duration_label']} | {record['language_detected']} | "
        f"segments {record['segments']} | chunks {record['chunks']} | {record['status']}"
    )


def chunk_choice_label(chunk: dict) -> str:
    snippet = chunk.get("text", "").strip().replace("\n", " ")
    if len(snippet) > 90:
        snippet = snippet[:87] + "..."
    return f"Chunk {chunk['index'] + 1} | {format_seconds(chunk['start'])}-{format_seconds(chunk['end'])} | {snippet}"


def search_choice_label(result: dict) -> str:
    return (
        f"Chunk {result['chunk_index'] + 1} | {format_seconds(result['start'])}-{format_seconds(result['end'])} | "
        f"{result['match_snippet'] or result['text'][:100]}"
    )


def citation_choice_label(citation: dict) -> str:
    return (
        f"Chunk {citation['chunk_index'] + 1} | {format_seconds(citation['start'])}-{format_seconds(citation['end'])} | "
        f"{citation['support_summary']}"
    )


def build_history_choices(records: list[dict]) -> list[tuple[str, str]]:
    return [(history_choice_label(record), record["job_id"]) for record in records]


def history_summary_markdown(records: list[dict]) -> str:
    if not records:
        return "## 历史纪录\n\n还没有处理纪录。先在左侧处理一个本地视频。"

    lines = [
        "## 历史纪录 / 视频库",
        "",
        f"- 可用单视频纪录：`{len(records)}`",
        "- 点击下面任一纪录，就能进入当前视频详情页、搜索与问答。",
        "",
    ]
    for record in records[:8]:
        lines.append(
            f"- `{record['source_title']}` · {record['created_at'] or 'unknown time'} · "
            f"{record['duration_label']} · {record['language_detected']} · "
            f"segments {record['segments']} · chunks {record['chunks']} · {record['status']}"
        )
    if len(records) > 8:
        lines.append(f"- ... 还有 {len(records) - 8} 条更早的纪录")
    return "\n".join(lines)


def empty_chunk_browser_message() -> str:
    return "## 当前视频内容\n\n先从历史纪录里选一个视频，或先处理一个新视频。"


def empty_search_message() -> str:
    return "## 内容搜索\n\n输入关键词后，这里会显示当前视频的命中 chunk。"


def empty_qa_message() -> str:
    return (
        "## 问答区\n\n"
        "问题会只基于当前视频的 chunks 回答。\n\n"
        "- 先在下方 QA 设置里填好 OpenAI 兼容接口\n"
        "- 再输入问题\n"
        "- 若检索不到足够依据，系统会明确提示依据不足"
    )


def detail_overview_markdown(bundle: dict) -> str:
    manifest = bundle["manifest"]
    counts = manifest.get("counts", {})
    lines = [
        f"## {manifest.get('source_title')}",
        "",
        "- 当前视频详情页已经直接连到 chunk / 搜索 / QA，不需要你先打开文件系统。",
        "",
        "### 概览信息",
        "",
        f"- 标题：`{manifest.get('source_title')}`",
        f"- 语言：`{manifest.get('language_detected', 'unknown')}`",
        f"- 时长：`{format_seconds(manifest.get('duration_seconds'))}`",
        f"- 处理时间：`{manifest.get('created_at', 'unknown')}`",
        f"- Segments：`{counts.get('segments', 0)}`",
        f"- Chunks：`{counts.get('chunks', 0)}`",
        "",
        "### 当前可下载文件",
        "",
        f"- `preview.md`：第一次整体查看结果",
        f"- `text.txt`：纯文本阅读与复制",
        f"- `chunks.json`：当前视频的搜索 / QA / 后续检索基础",
        f"- `manifest.json`：当前视频的一次运行摘要",
    ]
    return "\n".join(lines)


def build_artifact_downloads(bundle: dict) -> list[str]:
    artifact_paths = bundle["manifest"].get("artifact_paths", {})
    keys = [
        "preview_markdown",
        "text_txt",
        "transcript_json",
        "chunks_json",
        "metadata_json",
        "manifest_json",
    ]
    downloads = []
    for key in keys:
        path = artifact_paths.get(key)
        if path:
            downloads.append(path)
    return downloads


def selected_chunk_markdown(bundle: dict, selected_chunk_id: str) -> str:
    chunk = bundle["chunk_map"].get(selected_chunk_id)
    if not chunk:
        return empty_chunk_browser_message()

    return "\n".join(
        [
            "## 当前定位 chunk",
            "",
            f"- Chunk：`{chunk['index'] + 1}`",
            f"- 时间段：`{format_seconds(chunk['start'])} - {format_seconds(chunk['end'])}`",
            f"- Segment 范围：`{chunk['segment_start_index']} - {chunk['segment_end_index']}`",
            "",
            chunk["text"],
            "",
            "### 全部 chunk 浏览",
            "",
            "下方列表可切换；搜索结果或引用也会把这里同步定位到对应 chunk。",
        ]
    )


def initial_chunk_id(bundle: dict) -> str:
    chunks = bundle["chunks"].get("chunks", [])
    return chunks[0]["chunk_id"] if chunks else ""


def build_chunk_selector_update(bundle: dict, selected_chunk_id: str):
    choices = [(chunk_choice_label(chunk), chunk["chunk_id"]) for chunk in bundle["chunks"].get("chunks", [])]
    value = selected_chunk_id or (choices[0][1] if choices else None)
    return gr.update(choices=choices, value=value)


def build_search_results_update(results: list[dict], selected_chunk_id: Optional[str] = None):
    if not results:
        return gr.update(choices=[], value=None)
    choices = [(search_choice_label(result), result["chunk_id"]) for result in results]
    value = selected_chunk_id if selected_chunk_id else None
    if value and value not in {choice[1] for choice in choices}:
        value = None
    return gr.update(choices=choices, value=value)


def build_citation_update(citations: list[dict], selected_chunk_id: Optional[str] = None):
    if not citations:
        return gr.update(choices=[], value=None)
    choices = [(citation_choice_label(citation), citation["chunk_id"]) for citation in citations]
    value = selected_chunk_id if selected_chunk_id else None
    if value and value not in {choice[1] for choice in choices}:
        value = None
    return gr.update(choices=choices, value=value)


def empty_detail_outputs():
    return (
        None,
        {},
        "## 当前视频详情\n\n先在左侧处理一个视频，或从历史纪录中选一个视频。",
        gr.update(choices=[], value=None),
        empty_chunk_browser_message(),
        [],
        empty_search_message(),
        gr.update(choices=[], value=None),
        empty_qa_message(),
        "",
        gr.update(choices=[], value=None),
        None,
        "",
        None,
    )


def load_selected_video(job_id: str):
    if not job_id:
        return empty_detail_outputs()

    try:
        bundle = load_video_bundle(job_id, DEFAULT_OUTPUT_DIR)
    except VideoRagError as exc:
        return (
            job_id,
            {},
            f"## 当前视频详情\n\n加载失败：\n\n{exc}",
            gr.update(choices=[], value=None),
            empty_chunk_browser_message(),
            [],
            empty_search_message(),
            gr.update(choices=[], value=None),
            empty_qa_message(),
            "",
            gr.update(choices=[], value=None),
            None,
            "",
            None,
        )

    selected_chunk_id = initial_chunk_id(bundle)
    return (
        job_id,
        bundle,
        detail_overview_markdown(bundle),
        build_chunk_selector_update(bundle, selected_chunk_id),
        selected_chunk_markdown(bundle, selected_chunk_id),
        build_artifact_downloads(bundle),
        empty_search_message(),
        gr.update(choices=[], value=None),
        empty_qa_message(),
        "",
        gr.update(choices=[], value=None),
        None,
        "",
        None,
    )


def refresh_library(selected_job_id: Optional[str] = None):
    records = load_history_records(DEFAULT_OUTPUT_DIR)
    choices = build_history_choices(records)
    chosen_job_id = selected_job_id
    if choices and not chosen_job_id:
        chosen_job_id = choices[0][1]
    if choices and chosen_job_id not in {choice[1] for choice in choices}:
        chosen_job_id = choices[0][1]

    detail_outputs = load_selected_video(chosen_job_id) if chosen_job_id else empty_detail_outputs()
    return (
        history_summary_markdown(records),
        gr.update(choices=choices, value=chosen_job_id),
        *detail_outputs,
    )


def render_processing_status(result: dict) -> str:
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
            "### Next step",
            "",
            "- 现在可以切到「历史纪录 / 当前视频」工作区继续搜索、查看时间段、或直接提问。",
        ]
    )


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
        history_summary, history_radio, *detail_outputs = refresh_library(None)
        return (
            error_markdown,
            "\n".join(logs),
            "",
            "",
            "",
            [],
            history_summary,
            history_radio,
            *detail_outputs,
        )
    except Exception as exc:
        error_markdown = "\n".join(
            [
                "## Processing failed",
                "",
                f"Unexpected error: {exc}",
            ]
        )
        history_summary, history_radio, *detail_outputs = refresh_library(None)
        return (
            error_markdown,
            "\n".join(logs),
            "",
            "",
            "",
            [],
            history_summary,
            history_radio,
            *detail_outputs,
        )

    history_summary, history_radio, *detail_outputs = refresh_library(result["job_id"])
    return (
        render_processing_status(result),
        "\n".join(logs),
        result["transcript_text"],
        build_chunk_preview_markdown(result["chunks"], max_chunks=20),
        result["preview_markdown"],
        build_artifact_downloads(
            {
                "metadata": result["metadata"],
                "manifest": result["manifest"],
            }
        ),
        history_summary,
        history_radio,
        *detail_outputs,
    )


def on_history_selected(job_id: str):
    history_summary, history_radio, *detail_outputs = refresh_library(job_id)
    return history_summary, history_radio, *detail_outputs


def on_chunk_selected(bundle: dict, chunk_id: str):
    if not bundle or not chunk_id:
        return empty_chunk_browser_message()
    return selected_chunk_markdown(bundle, chunk_id)


def search_current_video(bundle: dict, query: str):
    if not bundle:
        return "## 内容搜索\n\n先选一个视频。", gr.update(choices=[], value=None)
    if not query.strip():
        return "## 内容搜索\n\n请输入关键词。", gr.update(choices=[], value=None)

    results = search_chunk_artifact(query, bundle["chunks"], limit=DEFAULT_SEARCH_LIMIT)
    if not results:
        return (
            f"## 内容搜索\n\n没有在当前视频中命中 `{query}`。",
            gr.update(choices=[], value=None),
        )

    header = "\n".join(
        [
            "## 内容搜索",
            "",
            f"- 查询词：`{query}`",
            f"- 命中结果：`{len(results)}`",
            "- 点击下面任一结果，会把 chunk 浏览区定位到对应时间段。",
        ]
    )
    return header, build_search_results_update(results)


def on_search_result_selected(bundle: dict, selected_chunk_id: str):
    if not bundle or not selected_chunk_id:
        return gr.update(), empty_chunk_browser_message()
    return build_chunk_selector_update(bundle, selected_chunk_id), selected_chunk_markdown(bundle, selected_chunk_id)


def ask_question_for_video(bundle: dict, question: str, base_url: str, model: str, api_key: str):
    if not bundle:
        return "## 问答区\n\n先选一个视频。", "", gr.update(choices=[], value=None), None

    try:
        qa_result = run_grounded_qa(
            question=question,
            video_bundle=bundle,
            base_url=base_url,
            model=model,
            api_key=api_key,
            top_k=DEFAULT_QA_RETRIEVAL_LIMIT,
        )
    except VideoRagError as exc:
        return f"## 问答区\n\n{exc}", "", gr.update(choices=[], value=None), None

    qa_status = [
        "## 问答区",
        "",
        f"- 问题：`{qa_result['question']}`",
        f"- 依据是否充足：`{'否' if qa_result['insufficient_evidence'] else '是'}`",
    ]
    if qa_result.get("retrieved_results"):
        qa_status.append(f"- 检索命中 chunks：`{len(qa_result['retrieved_results'])}`")

    answer_lines = [
        "## 答案",
        "",
        qa_result["answer"],
    ]
    if qa_result["insufficient_evidence"]:
        answer_lines.extend(
            [
                "",
                "> 当前答案已明确标记为依据不足，没有强行扩写。",
            ]
        )
        return "\n".join(qa_status), "\n".join(answer_lines), gr.update(choices=[], value=None), qa_result

    answer_lines.extend(
        [
            "",
            "### 引用说明",
            "",
            "点击下面的引用条目，会把 chunk 浏览区定位到对应时间段。",
        ]
    )
    return "\n".join(qa_status), "\n".join(answer_lines), build_citation_update(qa_result["citations"]), qa_result


def on_citation_selected(bundle: dict, selected_chunk_id: str):
    if not bundle or not selected_chunk_id:
        return gr.update(), empty_chunk_browser_message()
    return build_chunk_selector_update(bundle, selected_chunk_id), selected_chunk_markdown(bundle, selected_chunk_id)


def export_search(bundle: dict, query: str):
    if not bundle:
        return "请先选一个视频。", None
    if not query.strip():
        return "请先输入关键词，再导出搜索结果。", None
    results = search_chunk_artifact(query, bundle["chunks"], limit=DEFAULT_SEARCH_LIMIT)
    export_path = export_search_results(DEFAULT_OUTPUT_DIR, bundle, query, results)
    return f"已导出搜索结果：`{export_path.name}`", str(export_path)


def export_qa(bundle: dict, qa_result: dict):
    if not bundle:
        return "请先选一个视频。", None
    if not qa_result:
        return "请先完成一次问答。", None
    export_path = export_qa_result(DEFAULT_OUTPUT_DIR, bundle, qa_result)
    return f"已导出问答结果：`{export_path.name}`", str(export_path)


def export_summary(bundle: dict):
    if not bundle:
        return "请先选一个视频。", None
    export_path = export_video_summary(DEFAULT_OUTPUT_DIR, bundle)
    return f"已导出单视频摘要：`{export_path.name}`", str(export_path)


initial_history_summary, initial_history_radio, *initial_detail_outputs = refresh_library(None)

with gr.Blocks(title="video-rag", theme=gr.themes.Soft()) as demo:
    selected_job_state = gr.State(initial_detail_outputs[0])
    current_bundle_state = gr.State(initial_detail_outputs[1])
    qa_result_state = gr.State(None)

    gr.Markdown(
        """
        # video-rag

        把本地视频处理成可读文本之后，现在你还可以直接在同一个本地界面里浏览历史纪录、进入单视频详情、搜索内容、提问并查看对应时间段。

        这一轮的范围仍然只围绕**当前单视频**。它还不是完整 Video RAG 平台，但已经能跑通“处理 -> 查看 -> 搜索 -> grounded QA -> 匯出”的最小闭环。
        """
    )

    with gr.Tabs():
        with gr.Tab("处理新视频"):
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
                    process_status = gr.Markdown(
                        "## 等待开始\n\n处理完成后，这里会提示你下一步去视频库继续搜索或提问。"
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
                process_chunk_preview = gr.Markdown("处理完成后，这里会显示 chunk 预览。")

            with gr.Tab("结果页预览"):
                preview_markdown = gr.Markdown("处理完成后，这里会显示 `preview.md` 的内容。")

            with gr.Tab("文件下载"):
                processing_downloads = gr.File(label="当前处理产物", file_count="multiple")

        with gr.Tab("历史纪录 / 当前视频"):
            with gr.Row():
                with gr.Column(scale=1):
                    history_summary = gr.Markdown(initial_history_summary)
                    refresh_history_button = gr.Button("刷新历史纪录")
                    history_selector = gr.Radio(
                        label="历史纪录 / 视频库",
                        choices=initial_history_radio["choices"],
                        value=initial_history_radio["value"],
                    )
                with gr.Column(scale=1):
                    detail_overview = gr.Markdown(initial_detail_outputs[2])
                    artifact_downloads = gr.File(
                        label="当前视频文件下载",
                        file_count="multiple",
                        value=initial_detail_outputs[5],
                    )

            with gr.Row():
                with gr.Column(scale=1):
                    search_query = gr.Textbox(
                        label="当前视频关键词搜索",
                        placeholder="输入关键词，例如人物、主题、句子片段……",
                    )
                    search_button = gr.Button("搜索当前视频")
                    search_status = gr.Markdown(initial_detail_outputs[6])
                    search_results = gr.Radio(
                        label="命中结果",
                        choices=initial_detail_outputs[7]["choices"],
                        value=initial_detail_outputs[7]["value"],
                    )
                    export_search_button = gr.Button("匯出搜索结果")
                with gr.Column(scale=1):
                    with gr.Accordion("QA 设置（OpenAI 兼容接口）", open=False):
                        qa_base_url = gr.Textbox(
                            label="QA Base URL",
                            value=DEFAULT_QA_BASE_URL,
                            placeholder="例如 https://your-endpoint/v1",
                        )
                        qa_model = gr.Textbox(
                            label="QA Model",
                            value=DEFAULT_QA_MODEL,
                            placeholder="例如 gpt-4o-mini",
                        )
                        qa_api_key = gr.Textbox(
                            label="QA API Key",
                            value=DEFAULT_QA_API_KEY,
                            type="password",
                            placeholder="当前会话内保存，不写入磁盘",
                        )
                    question_input = gr.Textbox(
                        label="基于当前视频提问",
                        placeholder="例如：这段视频主要讲了什么？提到了哪些关键观点？",
                    )
                    ask_button = gr.Button("提问当前视频", variant="primary")
                    qa_status = gr.Markdown(initial_detail_outputs[8])
                    qa_answer = gr.Markdown(initial_detail_outputs[9] or "")
                    citation_results = gr.Radio(
                        label="引用",
                        choices=initial_detail_outputs[10]["choices"],
                        value=initial_detail_outputs[10]["value"],
                    )
                    export_qa_button = gr.Button("匯出问答结果")

            with gr.Row():
                with gr.Column(scale=1):
                    chunk_selector = gr.Radio(
                        label="Chunk / 时间段浏览",
                        choices=initial_detail_outputs[3]["choices"],
                        value=initial_detail_outputs[3]["value"],
                    )
                with gr.Column(scale=1):
                    current_chunk_markdown = gr.Markdown(initial_detail_outputs[4])

            with gr.Row():
                with gr.Column(scale=1):
                    export_summary_button = gr.Button("匯出单视频摘要")
                    export_status = gr.Markdown(initial_detail_outputs[12] or "")
                    export_file = gr.File(label="最新匯出文件", value=initial_detail_outputs[13])

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
            process_status,
            log_output,
            transcript_text,
            process_chunk_preview,
            preview_markdown,
            processing_downloads,
            history_summary,
            history_selector,
            selected_job_state,
            current_bundle_state,
            detail_overview,
            chunk_selector,
            current_chunk_markdown,
            artifact_downloads,
            search_status,
            search_results,
            qa_status,
            qa_answer,
            citation_results,
            qa_result_state,
            export_status,
            export_file,
        ],
        show_progress="full",
        show_api=False,
    )

    clear_button.click(
        fn=lambda: (
            "## 等待开始\n\n处理完成后，这里会提示你下一步去视频库继续搜索或提问。",
            "",
            "",
            "",
            "",
            [],
        ),
        outputs=[
            process_status,
            log_output,
            transcript_text,
            process_chunk_preview,
            preview_markdown,
            processing_downloads,
        ],
        show_api=False,
    )

    refresh_history_button.click(
        fn=refresh_library,
        inputs=[selected_job_state],
        outputs=[
            history_summary,
            history_selector,
            selected_job_state,
            current_bundle_state,
            detail_overview,
            chunk_selector,
            current_chunk_markdown,
            artifact_downloads,
            search_status,
            search_results,
            qa_status,
            qa_answer,
            citation_results,
            qa_result_state,
            export_status,
            export_file,
        ],
        show_api=False,
    )

    history_selector.select(
        fn=on_history_selected,
        inputs=[history_selector],
        outputs=[
            history_summary,
            history_selector,
            selected_job_state,
            current_bundle_state,
            detail_overview,
            chunk_selector,
            current_chunk_markdown,
            artifact_downloads,
            search_status,
            search_results,
            qa_status,
            qa_answer,
            citation_results,
            qa_result_state,
            export_status,
            export_file,
        ],
        show_api=False,
    )

    chunk_selector.select(
        fn=on_chunk_selected,
        inputs=[current_bundle_state, chunk_selector],
        outputs=[current_chunk_markdown],
        show_api=False,
    )

    search_button.click(
        fn=search_current_video,
        inputs=[current_bundle_state, search_query],
        outputs=[search_status, search_results],
        show_api=False,
    )

    search_results.select(
        fn=on_search_result_selected,
        inputs=[current_bundle_state, search_results],
        outputs=[chunk_selector, current_chunk_markdown],
        show_api=False,
    )

    ask_button.click(
        fn=ask_question_for_video,
        inputs=[current_bundle_state, question_input, qa_base_url, qa_model, qa_api_key],
        outputs=[qa_status, qa_answer, citation_results, qa_result_state],
        show_api=False,
    )

    citation_results.select(
        fn=on_citation_selected,
        inputs=[current_bundle_state, citation_results],
        outputs=[chunk_selector, current_chunk_markdown],
        show_api=False,
    )

    export_search_button.click(
        fn=export_search,
        inputs=[current_bundle_state, search_query],
        outputs=[export_status, export_file],
        show_api=False,
    )

    export_qa_button.click(
        fn=export_qa,
        inputs=[current_bundle_state, qa_result_state],
        outputs=[export_status, export_file],
        show_api=False,
    )

    export_summary_button.click(
        fn=export_summary,
        inputs=[current_bundle_state],
        outputs=[export_status, export_file],
        show_api=False,
    )


if __name__ == "__main__":
    demo.launch(
        server_name=DEFAULT_HOST,
        server_port=DEFAULT_PORT,
        show_api=False,
    )
