#!/usr/bin/env python3
"""Local Gradio app for video-rag personal video library MVP."""
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
    DEFAULT_LIBRARY_SEARCH_LIMIT,
    DEFAULT_QA_RETRIEVAL_LIMIT,
    DEFAULT_SEARCH_LIMIT,
    DEFAULT_WHISPER_MODEL,
    PipelineConfig,
    SUPPORTED_MODELS,
    VideoRagError,
    build_chunk_preview_markdown,
    export_qa_result,
    export_search_results,
    export_video_summary,
    filter_video_library_records,
    format_seconds,
    load_video_bundle,
    load_video_library_records,
    run_grounded_qa,
    run_pipeline,
    search_chunk_artifact,
    search_video_library,
    update_library_record,
)


DEFAULT_OUTPUT_DIR = ROOT / "data"
DEFAULT_HOST = os.getenv("VIDEO_RAG_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.getenv("VIDEO_RAG_PORT", "7860"))
DEFAULT_QA_BASE_URL = os.getenv("VIDEO_RAG_QA_BASE_URL", "")
DEFAULT_QA_MODEL = os.getenv("VIDEO_RAG_QA_MODEL", "")
DEFAULT_QA_API_KEY = os.getenv("VIDEO_RAG_QA_API_KEY", "")

DEFAULT_LANGUAGE_FILTER = "all"
DEFAULT_STAR_FILTER = "all"
DEFAULT_SORT_ORDER = "recent_desc"


def safe_file_list(paths):
    files = []
    for item in paths:
        if not item:
            continue
        path = Path(item)
        if path.exists():
            files.append(str(path))
    return files


def star_icon(starred: bool) -> str:
    return "★" if starred else "☆"


def library_choice_label(record: dict) -> str:
    display_title = record.get("display_title") or record.get("title") or record.get("video_id")
    return (
        f"{star_icon(record.get('starred', False))} {display_title} | "
        f"{record.get('created_at') or 'unknown time'} | "
        f"{format_seconds(record.get('duration_seconds'))} | "
        f"{record.get('language', 'unknown')} | "
        f"{record.get('status', 'completed')}"
    )


def chunk_choice_label(chunk: dict) -> str:
    snippet = chunk.get("text", "").strip().replace("\n", " ")
    if len(snippet) > 90:
        snippet = snippet[:87] + "..."
    return f"Chunk {chunk['index'] + 1} | {format_seconds(chunk['start'])}-{format_seconds(chunk['end'])} | {snippet}"


def search_choice_label(result: dict) -> str:
    return (
        f"Chunk {result['chunk_index'] + 1} | "
        f"{format_seconds(result['start'])}-{format_seconds(result['end'])} | "
        f"{result['match_snippet'] or result['text'][:100]}"
    )


def citation_choice_label(citation: dict) -> str:
    return (
        f"Chunk {citation['chunk_index'] + 1} | "
        f"{format_seconds(citation['start'])}-{format_seconds(citation['end'])} | "
        f"{citation['support_summary']}"
    )


def library_search_choice_label(result: dict) -> str:
    return (
        f"{result['display_title']} | Chunk {result['chunk_index'] + 1} | "
        f"{format_seconds(result['start'])}-{format_seconds(result['end'])} | "
        f"{result['match_snippet']}"
    )


def build_library_choices(records: list[dict]) -> list[tuple[str, str]]:
    return [(library_choice_label(record), record["video_id"]) for record in records]


def build_language_filter_update(all_records: list[dict], selected_language: str):
    languages = sorted({record.get("language", "unknown") for record in all_records if record.get("language")})
    choices = [("全部语言", DEFAULT_LANGUAGE_FILTER)] + [(language, language) for language in languages]
    valid_values = {value for _, value in choices}
    value = selected_language if selected_language in valid_values else DEFAULT_LANGUAGE_FILTER
    return gr.update(choices=choices, value=value)


def build_library_selector_update(records: list[dict], selected_video_id: Optional[str]):
    choices = build_library_choices(records)
    valid_ids = {value for _, value in choices}
    value = selected_video_id if selected_video_id in valid_ids else (choices[0][1] if choices else None)
    return gr.update(choices=choices, value=value)


def build_chunk_selector_update(bundle: dict, selected_chunk_id: Optional[str]):
    choices = [(chunk_choice_label(chunk), chunk["chunk_id"]) for chunk in bundle["chunks"].get("chunks", [])]
    valid_ids = {value for _, value in choices}
    value = selected_chunk_id if selected_chunk_id in valid_ids else (choices[0][1] if choices else None)
    return gr.update(choices=choices, value=value)


def build_search_results_update(results: list[dict], selected_chunk_id: Optional[str] = None):
    if not results:
        return gr.update(choices=[], value=None)
    choices = [(search_choice_label(result), result["chunk_id"]) for result in results]
    valid_ids = {value for _, value in choices}
    value = selected_chunk_id if selected_chunk_id in valid_ids else None
    return gr.update(choices=choices, value=value)


def build_citation_update(citations: list[dict], selected_chunk_id: Optional[str] = None):
    if not citations:
        return gr.update(choices=[], value=None)
    choices = [(citation_choice_label(citation), citation["chunk_id"]) for citation in citations]
    valid_ids = {value for _, value in choices}
    value = selected_chunk_id if selected_chunk_id in valid_ids else None
    return gr.update(choices=choices, value=value)


def build_library_search_results_update(results: list[dict], selected_result_id: Optional[str] = None):
    if not results:
        return gr.update(choices=[], value=None)
    choices = [(library_search_choice_label(result), result["result_id"]) for result in results]
    valid_ids = {value for _, value in choices}
    value = selected_result_id if selected_result_id in valid_ids else None
    return gr.update(choices=choices, value=value)


def empty_library_overview_markdown() -> str:
    return "## 个人视频库\n\n还没有可用视频。先到右侧“处理新视频”里处理一个本地视频。"


def render_library_overview_markdown(all_records: list[dict], visible_records: list[dict]) -> str:
    if not all_records:
        return empty_library_overview_markdown()

    lines = [
        "## 个人视频库",
        "",
        f"- 总资料数：`{len(all_records)}`",
        f"- 当前筛选后：`{len(visible_records)}`",
        "- 每条资料都代表一次本地处理结果；你可以收藏、改显示标题、加标签、写备注，并在以后再进入。",
        "",
    ]

    if not visible_records:
        lines.extend(
            [
                "当前筛选下没有结果。",
                "",
                "你可以调整标题关键词、语言、收藏状态或排序方式。",
            ]
        )
        return "\n".join(lines)

    for record in visible_records[:10]:
        tags = ", ".join(record.get("tags", [])) or "暂无"
        summary = record.get("summary", "") or "暂无摘要预览。"
        if len(summary) > 180:
            summary = summary[:177].rstrip() + "..."
        lines.extend(
            [
                f"### {star_icon(record.get('starred', False))} {record.get('display_title') or record.get('title')}",
                "",
                f"- 处理时间：`{record.get('created_at') or 'unknown'}`",
                f"- 时长：`{format_seconds(record.get('duration_seconds'))}`",
                f"- 语言：`{record.get('language', 'unknown')}`",
                f"- 状态：`{record.get('status', 'completed')}`",
                f"- 标签：`{tags}`",
                f"- 摘要预览：{summary}",
                "",
            ]
        )

    if len(visible_records) > 10:
        lines.append(f"_... 还有 {len(visible_records) - 10} 条资料未展开显示。_")
    return "\n".join(lines)


def empty_library_search_message() -> str:
    return (
        "## 跨视频关键词搜索\n\n"
        "这里会在当前筛选范围内搜索所有视频的 chunk 内容，并把结果直接定位回具体视频和时间段。"
    )


def empty_detail_summary() -> str:
    return "## 视频摘要卡\n\n先从视频库里选一个视频。"


def empty_detail_info() -> str:
    return "## 关键信息\n\n先从视频库里选一个视频。"


def empty_artifact_paths() -> str:
    return "## 本地文件入口\n\n当前还没有可展示的本地文件路径。"


def empty_saved_exports() -> str:
    return "## 已保存结果\n\n当前视频还没有历史保存记录。"


def empty_chunk_browser_message() -> str:
    return "## Chunk / 时间段浏览\n\n先从视频库里选一个视频。"


def empty_search_message(bundle: Optional[dict] = None) -> str:
    if not bundle:
        return "## 当前视频搜索\n\n先从视频库里选一个视频。"
    if not bundle.get("content_ready"):
        return "## 当前视频搜索\n\n这个视频目前缺少可用的 chunk artifact，所以还不能搜索。"
    return "## 当前视频搜索\n\n输入关键词后，这里会显示当前视频命中的 chunk。"


def empty_qa_message(bundle: Optional[dict] = None) -> str:
    if not bundle:
        return "## grounded QA\n\n先从视频库里选一个视频。"
    if not bundle.get("content_ready"):
        return "## grounded QA\n\n这个视频目前缺少可用的 chunk artifact，所以还不能提问。"
    return (
        "## grounded QA\n\n"
        "问题只会基于当前视频的 chunk 内容回答。\n\n"
        "- 先配置 OpenAI 兼容接口\n"
        "- 再输入问题\n"
        "- 若没有足够依据，系统会明确拒答"
    )


def summary_card_markdown(bundle: dict) -> str:
    record = bundle["library_record"]
    summary = record.get("summary") or "当前还没有可用的摘要预览。"
    return "\n".join(
        [
            "## 视频摘要卡",
            "",
            f"### {record.get('display_title') or record.get('title')}",
            "",
            summary,
        ]
    )


def key_info_markdown(bundle: dict) -> str:
    record = bundle["library_record"]
    manifest = bundle["manifest"]
    counts = manifest.get("counts", {})
    source_path = record.get("source_file_path") or "unknown"
    return "\n".join(
        [
            "## 关键信息区",
            "",
            f"- 原始标题：`{record.get('title')}`",
            f"- 显示标题：`{record.get('display_title') or record.get('title')}`",
            f"- 语言：`{record.get('language', 'unknown')}`",
            f"- 时长：`{format_seconds(record.get('duration_seconds'))}`",
            f"- 处理时间：`{record.get('created_at') or 'unknown'}`",
            f"- 最近更新：`{record.get('updated_at') or record.get('created_at') or 'unknown'}`",
            f"- 状态：`{record.get('status', 'completed')}`",
            f"- Segments：`{counts.get('segments', bundle['metadata'].get('transcript_segments', 0))}`",
            f"- Chunks：`{counts.get('chunks', bundle['metadata'].get('chunk_count', 0))}`",
            f"- 收藏：`{'是' if record.get('starred') else '否'}`",
            f"- 保存结果：`{len(record.get('saved_exports', []))}`",
            f"- 来源文件：`{source_path}`",
        ]
    )


def artifact_paths_markdown(bundle: dict) -> str:
    artifact_paths = bundle["library_record"].get("artifact_paths", {})
    exports_dir = artifact_paths.get("exports_dir") or bundle["paths"].get("exports_dir") or ""
    lines = [
        "## 本地文件入口",
        "",
        f"- `preview.md`：`{artifact_paths.get('preview_markdown', '')}`",
        f"- `text.txt`：`{artifact_paths.get('text_txt', '')}`",
        f"- `transcript.json`：`{artifact_paths.get('transcript_json', '')}`",
        f"- `chunks.json`：`{artifact_paths.get('chunks_json', '')}`",
        f"- `meta.json`：`{artifact_paths.get('metadata_json', '')}`",
        f"- `manifest.json`：`{artifact_paths.get('manifest_json', '')}`",
        f"- `video record`：`{artifact_paths.get('library_record_json', '')}`",
        f"- `exports/`：`{exports_dir}`",
    ]
    return "\n".join(lines)


def saved_exports_markdown(bundle: dict) -> str:
    saved_exports = bundle["library_record"].get("saved_exports", [])
    if not saved_exports:
        return empty_saved_exports()

    lines = [
        "## 已保存结果",
        "",
        "这些记录会保存在本地，并且和当前视频保持关联。",
        "",
    ]
    for export in saved_exports[:12]:
        lines.append(
            f"- `{export.get('type', 'export')}` · {export.get('created_at', 'unknown')} · `{Path(export.get('path', '')).name}`"
        )
    if len(saved_exports) > 12:
        lines.append(f"- ... 还有 {len(saved_exports) - 12} 条更早的保存记录")
    return "\n".join(lines)


def build_artifact_downloads(bundle: dict) -> list[str]:
    artifact_paths = bundle["library_record"].get("artifact_paths", {})
    keys = [
        "preview_markdown",
        "text_txt",
        "transcript_json",
        "chunks_json",
        "metadata_json",
        "manifest_json",
        "library_record_json",
    ]
    return safe_file_list([artifact_paths.get(key) for key in keys])


def build_saved_export_downloads(bundle: dict) -> list[str]:
    return safe_file_list([item.get("path") for item in bundle["library_record"].get("saved_exports", [])])


def selected_chunk_markdown(bundle: dict, selected_chunk_id: str) -> str:
    if not bundle.get("content_ready"):
        return "## Chunk / 时间段浏览\n\n这个视频目前没有可用的 chunk artifact，暂时不能做定位浏览。"
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
            "下方列表可切换；当前视频搜索、跨视频搜索、引用点击都会把这里同步定位到对应时间段。",
        ]
    )


def initial_chunk_id(bundle: dict) -> str:
    chunks = bundle["chunks"].get("chunks", [])
    return chunks[0]["chunk_id"] if chunks else ""


def detail_outputs_for_bundle(
    bundle: dict,
    *,
    selected_chunk_id: Optional[str] = None,
    organize_status: str = "",
    export_status: str = "",
    export_file: Optional[str] = None,
):
    record = bundle["library_record"]
    current_chunk_id = selected_chunk_id if selected_chunk_id in bundle["chunk_map"] else initial_chunk_id(bundle)
    return (
        bundle["video_id"],
        bundle,
        summary_card_markdown(bundle),
        key_info_markdown(bundle),
        artifact_paths_markdown(bundle),
        build_artifact_downloads(bundle),
        record.get("display_title") or record.get("title") or bundle["video_id"],
        ", ".join(record.get("tags", [])),
        record.get("notes", ""),
        bool(record.get("starred", False)),
        organize_status,
        saved_exports_markdown(bundle),
        build_saved_export_downloads(bundle),
        empty_search_message(bundle),
        gr.update(choices=[], value=None),
        empty_qa_message(bundle),
        "",
        gr.update(choices=[], value=None),
        build_chunk_selector_update(bundle, current_chunk_id),
        selected_chunk_markdown(bundle, current_chunk_id),
        export_status,
        export_file,
    )


def empty_detail_outputs(
    *,
    organize_status: str = "",
    export_status: str = "",
    export_file: Optional[str] = None,
):
    return (
        None,
        {},
        empty_detail_summary(),
        empty_detail_info(),
        empty_artifact_paths(),
        [],
        "",
        "",
        "",
        False,
        organize_status,
        empty_saved_exports(),
        [],
        empty_search_message(),
        gr.update(choices=[], value=None),
        empty_qa_message(),
        "",
        gr.update(choices=[], value=None),
        gr.update(choices=[], value=None),
        empty_chunk_browser_message(),
        export_status,
        export_file,
    )


def load_detail_view(
    video_id: Optional[str],
    *,
    selected_chunk_id: Optional[str] = None,
    organize_status: str = "",
    export_status: str = "",
    export_file: Optional[str] = None,
):
    if not video_id:
        return empty_detail_outputs(
            organize_status=organize_status,
            export_status=export_status,
            export_file=export_file,
        )

    try:
        bundle = load_video_bundle(video_id, DEFAULT_OUTPUT_DIR)
    except VideoRagError as exc:
        return (
            video_id,
            {},
            "## 视频摘要卡\n\n加载失败。",
            f"## 关键信息\n\n{exc}",
            empty_artifact_paths(),
            [],
            "",
            "",
            "",
            False,
            organize_status,
            empty_saved_exports(),
            [],
            empty_search_message(),
            gr.update(choices=[], value=None),
            empty_qa_message(),
            "",
            gr.update(choices=[], value=None),
            gr.update(choices=[], value=None),
            empty_chunk_browser_message(),
            export_status,
            export_file,
        )

    return detail_outputs_for_bundle(
        bundle,
        selected_chunk_id=selected_chunk_id,
        organize_status=organize_status,
        export_status=export_status,
        export_file=export_file,
    )


def refresh_library_workspace(
    title_filter: str,
    language_filter: str,
    starred_filter: str,
    sort_order: str,
    selected_video_id: Optional[str] = None,
):
    all_records = load_video_library_records(DEFAULT_OUTPUT_DIR)
    filtered_records = filter_video_library_records(
        all_records,
        title_query=title_filter,
        language=language_filter,
        starred=starred_filter,
        sort_order=sort_order,
    )
    selector_update = build_library_selector_update(filtered_records, selected_video_id)
    chosen_video_id = selector_update["value"]
    detail_outputs = load_detail_view(chosen_video_id)
    return (
        filtered_records,
        render_library_overview_markdown(all_records, filtered_records),
        build_language_filter_update(all_records, language_filter),
        selector_update,
        empty_library_search_message(),
        gr.update(choices=[], value=None),
        [],
        *detail_outputs,
    )


def reset_filters_and_refresh():
    workspace_outputs = refresh_library_workspace("", DEFAULT_LANGUAGE_FILTER, DEFAULT_STAR_FILTER, DEFAULT_SORT_ORDER)
    return (
        "",
        DEFAULT_STAR_FILTER,
        DEFAULT_SORT_ORDER,
        *workspace_outputs,
    )


def render_processing_status(result: dict) -> str:
    metadata = result["metadata"]
    manifest = result["manifest"]
    counts = manifest["counts"]
    return "\n".join(
        [
            "## 处理完成",
            "",
            f"- 标题：`{metadata['title']}`",
            f"- 语言：`{manifest['language_detected']}`",
            f"- 时长：`{format_seconds(manifest['duration_seconds'])}`",
            f"- Segments：`{counts['segments']}`",
            f"- Chunks：`{counts['chunks']}`",
            "",
            "### 下一步",
            "",
            "- 现在可以切到「个人视频库」继续整理、跨视频搜索、或进入详情页提问。",
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
        reset_outputs = reset_filters_and_refresh()
        return (
            f"## 处理失败\n\n{exc}",
            "\n".join(logs),
            "",
            "",
            "",
            [],
            *reset_outputs,
        )
    except Exception as exc:
        reset_outputs = reset_filters_and_refresh()
        return (
            f"## 处理失败\n\nUnexpected error: {exc}",
            "\n".join(logs),
            "",
            "",
            "",
            [],
            *reset_outputs,
        )

    workspace_outputs = refresh_library_workspace(
        "",
        DEFAULT_LANGUAGE_FILTER,
        DEFAULT_STAR_FILTER,
        DEFAULT_SORT_ORDER,
        result["job_id"],
    )
    return (
        render_processing_status(result),
        "\n".join(logs),
        result["transcript_text"],
        build_chunk_preview_markdown(result["chunks"], max_chunks=20),
        result["preview_markdown"],
        build_artifact_downloads(
            {
                "library_record": result["library_record"],
                "paths": {
                    "exports_dir": str((DEFAULT_OUTPUT_DIR / "exports" / result["job_id"]).resolve()),
                },
            }
        ),
        "",
        DEFAULT_STAR_FILTER,
        DEFAULT_SORT_ORDER,
        *workspace_outputs,
    )


def on_library_selected(video_id: str):
    return load_detail_view(video_id)


def save_video_organization(
    selected_video_id: str,
    display_title: str,
    tags_text: str,
    notes_text: str,
    starred: bool,
    title_filter: str,
    language_filter: str,
    starred_filter: str,
    sort_order: str,
):
    if not selected_video_id:
        return refresh_library_workspace(title_filter, language_filter, starred_filter, sort_order)

    update_library_record(
        DEFAULT_OUTPUT_DIR,
        selected_video_id,
        display_title=display_title,
        tags=tags_text,
        notes=notes_text,
        starred=starred,
    )
    filtered_records, library_overview, language_update, selector_update, library_search_status, library_search_results, library_search_state, *_ = refresh_library_workspace(
        title_filter,
        language_filter,
        starred_filter,
        sort_order,
        selected_video_id,
    )
    detail_outputs = load_detail_view(selected_video_id, organize_status="已保存当前视频的整理信息。")
    return (
        filtered_records,
        library_overview,
        language_update,
        selector_update,
        library_search_status,
        library_search_results,
        library_search_state,
        *detail_outputs,
    )


def search_library(filtered_records: list[dict], query: str):
    if not filtered_records:
        return "## 跨视频关键词搜索\n\n当前筛选范围里没有可搜索的视频。", gr.update(choices=[], value=None), []
    if not query.strip():
        return "## 跨视频关键词搜索\n\n请输入关键词。", gr.update(choices=[], value=None), []

    results = search_video_library(query, filtered_records, limit=DEFAULT_LIBRARY_SEARCH_LIMIT)
    if not results:
        return (
            f"## 跨视频关键词搜索\n\n当前筛选范围内没有命中 `{query}` 的视频内容。",
            gr.update(choices=[], value=None),
            [],
        )

    header = "\n".join(
        [
            "## 跨视频关键词搜索",
            "",
            f"- 查询词：`{query}`",
            f"- 命中结果：`{len(results)}`",
            "- 点击下面任一结果，会自动跳回对应视频详情页并定位到时间段。",
        ]
    )
    return header, build_library_search_results_update(results), results


def on_library_search_result_selected(results: list[dict], result_id: str):
    if not results or not result_id:
        return (
            gr.update(),
            *empty_detail_outputs(),
        )

    selected = next((item for item in results if item["result_id"] == result_id), None)
    if not selected:
        return (
            gr.update(),
            *empty_detail_outputs(),
        )

    detail_outputs = load_detail_view(selected["video_id"], selected_chunk_id=selected["chunk_id"])
    return (
        gr.update(value=selected["video_id"]),
        *detail_outputs,
    )


def search_current_video(bundle: dict, query: str):
    if not bundle:
        return "## 当前视频搜索\n\n先选一个视频。", gr.update(choices=[], value=None)
    if not bundle.get("content_ready"):
        return "## 当前视频搜索\n\n这个视频目前没有可用的 chunk artifact，所以不能搜索。", gr.update(choices=[], value=None)
    if not query.strip():
        return "## 当前视频搜索\n\n请输入关键词。", gr.update(choices=[], value=None)

    results = search_chunk_artifact(query, bundle["chunks"], limit=DEFAULT_SEARCH_LIMIT)
    if not results:
        return (
            f"## 当前视频搜索\n\n没有在当前视频中命中 `{query}`。",
            gr.update(choices=[], value=None),
        )

    header = "\n".join(
        [
            "## 当前视频搜索",
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


def on_chunk_selected(bundle: dict, selected_chunk_id: str):
    if not bundle or not selected_chunk_id:
        return empty_chunk_browser_message()
    return selected_chunk_markdown(bundle, selected_chunk_id)


def ask_question_for_video(bundle: dict, question: str, base_url: str, model: str, api_key: str):
    if not bundle:
        return "## grounded QA\n\n先选一个视频。", "", gr.update(choices=[], value=None), None
    if not bundle.get("content_ready"):
        return "## grounded QA\n\n这个视频目前没有可用的 chunk artifact，所以不能提问。", "", gr.update(choices=[], value=None), None

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
        return f"## grounded QA\n\n{exc}", "", gr.update(choices=[], value=None), None

    qa_status = [
        "## grounded QA",
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
        return load_detail_view(None, export_status="请先选一个视频。")
    if not bundle.get("content_ready"):
        return load_detail_view(bundle["video_id"], export_status="当前视频没有可导出的搜索内容。")
    if not query.strip():
        return load_detail_view(bundle["video_id"], export_status="请先输入关键词，再保存搜索结果。")

    results = search_chunk_artifact(query, bundle["chunks"], limit=DEFAULT_SEARCH_LIMIT)
    export_path = export_search_results(DEFAULT_OUTPUT_DIR, bundle, query, results)
    return load_detail_view(
        bundle["video_id"],
        export_status=f"已保存搜索结果：`{export_path.name}`",
        export_file=str(export_path),
    )


def export_qa(bundle: dict, qa_result: dict):
    if not bundle:
        return load_detail_view(None, export_status="请先选一个视频。")
    if not qa_result:
        return load_detail_view(bundle["video_id"], export_status="请先完成一次问答，再保存结果。")

    export_path = export_qa_result(DEFAULT_OUTPUT_DIR, bundle, qa_result)
    return load_detail_view(
        bundle["video_id"],
        export_status=f"已保存问答结果：`{export_path.name}`",
        export_file=str(export_path),
    )


def export_summary(bundle: dict):
    if not bundle:
        return load_detail_view(None, export_status="请先选一个视频。")

    export_path = export_video_summary(DEFAULT_OUTPUT_DIR, bundle)
    return load_detail_view(
        bundle["video_id"],
        export_status=f"已保存单视频摘要：`{export_path.name}`",
        export_file=str(export_path),
    )


(
    initial_filtered_records,
    initial_library_overview,
    initial_language_filter,
    initial_library_selector,
    initial_library_search_status,
    initial_library_search_results,
    initial_library_search_state,
    *initial_detail_outputs,
) = refresh_library_workspace("", DEFAULT_LANGUAGE_FILTER, DEFAULT_STAR_FILTER, DEFAULT_SORT_ORDER)


with gr.Blocks(title="video-rag", theme=gr.themes.Soft()) as demo:
    filtered_records_state = gr.State(initial_filtered_records)
    library_search_results_state = gr.State(initial_library_search_state)
    selected_video_state = gr.State(initial_detail_outputs[0])
    current_bundle_state = gr.State(initial_detail_outputs[1])
    qa_result_state = gr.State(None)

    gr.Markdown(
        """
        # video-rag

        `video-rag` 现在已经从“本地单视频处理工具”推进到 **本地个人视频资料库 MVP**。

        你可以在本地持续处理多个视频，把它们沉淀成可找回、可整理、可再次进入的个人资料库：

        - 处理多个本地视频
        - 在视频库中按标题、语言、收藏状态筛选
        - 跨视频做基础关键词搜索
        - 进入某个视频详情页继续搜索、grounded QA、保存结果
        - 对视频做最基本的整理：收藏、改显示标题、加标签、写备注

        它仍然**不是**完整 Video RAG 平台。本轮重点是把“资料库层”做稳，为后续 multi-video knowledge loop 打基础。
        """
    )

    with gr.Tabs():
        with gr.Tab("个人视频库"):
            with gr.Row():
                title_filter = gr.Textbox(label="标题关键词", placeholder="按显示标题 / 原始标题 / 标签筛选")
                language_filter = gr.Dropdown(
                    label="语言",
                    choices=initial_language_filter["choices"],
                    value=initial_language_filter["value"],
                )
                starred_filter = gr.Dropdown(
                    label="收藏状态",
                    choices=[
                        ("全部", DEFAULT_STAR_FILTER),
                        ("只看收藏", "starred"),
                        ("只看未收藏", "unstarred"),
                    ],
                    value=DEFAULT_STAR_FILTER,
                )
                sort_order = gr.Dropdown(
                    label="排序",
                    choices=[
                        ("最近处理（新到旧）", "recent_desc"),
                        ("最近处理（旧到新）", "recent_asc"),
                        ("显示标题 A-Z", "title_asc"),
                    ],
                    value=DEFAULT_SORT_ORDER,
                )
                apply_filters_button = gr.Button("应用筛选", variant="primary")
                clear_filters_button = gr.Button("清空筛选")

            library_overview = gr.Markdown(initial_library_overview)
            library_selector = gr.Radio(
                label="选择视频",
                choices=initial_library_selector["choices"],
                value=initial_library_selector["value"],
            )

            with gr.Row():
                with gr.Column(scale=1):
                    library_search_query = gr.Textbox(
                        label="跨视频关键词搜索",
                        placeholder="在当前筛选范围内搜索所有视频的 chunk 内容",
                    )
                    library_search_button = gr.Button("搜索视频库")
                    library_search_status = gr.Markdown(initial_library_search_status)
                    library_search_results = gr.Radio(
                        label="跨视频搜索结果",
                        choices=initial_library_search_results["choices"],
                        value=initial_library_search_results["value"],
                    )
                with gr.Column(scale=1):
                    summary_card = gr.Markdown(initial_detail_outputs[2])
                    key_info = gr.Markdown(initial_detail_outputs[3])

            with gr.Row():
                with gr.Column(scale=1):
                    display_title_input = gr.Textbox(label="显示标题", value=initial_detail_outputs[6])
                    tags_input = gr.Textbox(label="标签（逗号分隔）", value=initial_detail_outputs[7])
                    starred_checkbox = gr.Checkbox(label="收藏这条视频资料", value=initial_detail_outputs[9])
                    save_organization_button = gr.Button("保存整理信息")
                    organize_status = gr.Markdown(initial_detail_outputs[10] or "")
                with gr.Column(scale=1):
                    notes_input = gr.Textbox(
                        label="我的备注",
                        value=initial_detail_outputs[8],
                        lines=8,
                        max_lines=12,
                        show_copy_button=True,
                    )

            with gr.Row():
                with gr.Column(scale=1):
                    artifact_paths = gr.Markdown(initial_detail_outputs[4])
                    artifact_downloads = gr.File(
                        label="当前视频本地文件",
                        file_count="multiple",
                        value=initial_detail_outputs[5],
                    )
                with gr.Column(scale=1):
                    saved_exports = gr.Markdown(initial_detail_outputs[11])
                    saved_export_downloads = gr.File(
                        label="历史保存结果",
                        file_count="multiple",
                        value=initial_detail_outputs[12],
                    )

            with gr.Row():
                with gr.Column(scale=1):
                    search_query = gr.Textbox(
                        label="当前视频关键词搜索",
                        placeholder="输入关键词，例如人物、主题、句子片段……",
                    )
                    search_button = gr.Button("搜索当前视频")
                    search_status = gr.Markdown(initial_detail_outputs[13])
                    search_results = gr.Radio(
                        label="当前视频命中结果",
                        choices=initial_detail_outputs[14]["choices"],
                        value=initial_detail_outputs[14]["value"],
                    )
                    export_search_button = gr.Button("保存搜索结果")
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
                    qa_status = gr.Markdown(initial_detail_outputs[15])
                    qa_answer = gr.Markdown(initial_detail_outputs[16] or "")
                    citation_results = gr.Radio(
                        label="引用",
                        choices=initial_detail_outputs[17]["choices"],
                        value=initial_detail_outputs[17]["value"],
                    )
                    export_qa_button = gr.Button("保存问答结果")

            with gr.Row():
                with gr.Column(scale=1):
                    chunk_selector = gr.Radio(
                        label="Chunk / 时间段浏览",
                        choices=initial_detail_outputs[18]["choices"],
                        value=initial_detail_outputs[18]["value"],
                    )
                with gr.Column(scale=1):
                    current_chunk_markdown = gr.Markdown(initial_detail_outputs[19])

            with gr.Row():
                with gr.Column(scale=1):
                    export_summary_button = gr.Button("保存单视频摘要")
                    export_status = gr.Markdown(initial_detail_outputs[20] or "")
                    export_file = gr.File(label="最新保存结果", value=initial_detail_outputs[21])

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
                        "## 等待开始\n\n处理完成后，这里会提示你回到“个人视频库”继续整理、搜索和提问。"
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

    apply_filters_button.click(
        fn=refresh_library_workspace,
        inputs=[title_filter, language_filter, starred_filter, sort_order, selected_video_state],
        outputs=[
            filtered_records_state,
            library_overview,
            language_filter,
            library_selector,
            library_search_status,
            library_search_results,
            library_search_results_state,
            selected_video_state,
            current_bundle_state,
            summary_card,
            key_info,
            artifact_paths,
            artifact_downloads,
            display_title_input,
            tags_input,
            notes_input,
            starred_checkbox,
            organize_status,
            saved_exports,
            saved_export_downloads,
            search_status,
            search_results,
            qa_status,
            qa_answer,
            citation_results,
            chunk_selector,
            current_chunk_markdown,
            export_status,
            export_file,
        ],
        show_api=False,
    )

    clear_filters_button.click(
        fn=reset_filters_and_refresh,
        outputs=[
            title_filter,
            starred_filter,
            sort_order,
            filtered_records_state,
            library_overview,
            language_filter,
            library_selector,
            library_search_status,
            library_search_results,
            library_search_results_state,
            selected_video_state,
            current_bundle_state,
            summary_card,
            key_info,
            artifact_paths,
            artifact_downloads,
            display_title_input,
            tags_input,
            notes_input,
            starred_checkbox,
            organize_status,
            saved_exports,
            saved_export_downloads,
            search_status,
            search_results,
            qa_status,
            qa_answer,
            citation_results,
            chunk_selector,
            current_chunk_markdown,
            export_status,
            export_file,
        ],
        show_api=False,
    )

    library_selector.select(
        fn=on_library_selected,
        inputs=[library_selector],
        outputs=[
            selected_video_state,
            current_bundle_state,
            summary_card,
            key_info,
            artifact_paths,
            artifact_downloads,
            display_title_input,
            tags_input,
            notes_input,
            starred_checkbox,
            organize_status,
            saved_exports,
            saved_export_downloads,
            search_status,
            search_results,
            qa_status,
            qa_answer,
            citation_results,
            chunk_selector,
            current_chunk_markdown,
            export_status,
            export_file,
        ],
        show_api=False,
    )

    save_organization_button.click(
        fn=save_video_organization,
        inputs=[
            selected_video_state,
            display_title_input,
            tags_input,
            notes_input,
            starred_checkbox,
            title_filter,
            language_filter,
            starred_filter,
            sort_order,
        ],
        outputs=[
            filtered_records_state,
            library_overview,
            language_filter,
            library_selector,
            library_search_status,
            library_search_results,
            library_search_results_state,
            selected_video_state,
            current_bundle_state,
            summary_card,
            key_info,
            artifact_paths,
            artifact_downloads,
            display_title_input,
            tags_input,
            notes_input,
            starred_checkbox,
            organize_status,
            saved_exports,
            saved_export_downloads,
            search_status,
            search_results,
            qa_status,
            qa_answer,
            citation_results,
            chunk_selector,
            current_chunk_markdown,
            export_status,
            export_file,
        ],
        show_api=False,
    )

    library_search_button.click(
        fn=search_library,
        inputs=[filtered_records_state, library_search_query],
        outputs=[library_search_status, library_search_results, library_search_results_state],
        show_api=False,
    )

    library_search_results.select(
        fn=on_library_search_result_selected,
        inputs=[library_search_results_state, library_search_results],
        outputs=[
            library_selector,
            selected_video_state,
            current_bundle_state,
            summary_card,
            key_info,
            artifact_paths,
            artifact_downloads,
            display_title_input,
            tags_input,
            notes_input,
            starred_checkbox,
            organize_status,
            saved_exports,
            saved_export_downloads,
            search_status,
            search_results,
            qa_status,
            qa_answer,
            citation_results,
            chunk_selector,
            current_chunk_markdown,
            export_status,
            export_file,
        ],
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

    chunk_selector.select(
        fn=on_chunk_selected,
        inputs=[current_bundle_state, chunk_selector],
        outputs=[current_chunk_markdown],
        show_api=False,
    )

    export_search_button.click(
        fn=export_search,
        inputs=[current_bundle_state, search_query],
        outputs=[
            selected_video_state,
            current_bundle_state,
            summary_card,
            key_info,
            artifact_paths,
            artifact_downloads,
            display_title_input,
            tags_input,
            notes_input,
            starred_checkbox,
            organize_status,
            saved_exports,
            saved_export_downloads,
            search_status,
            search_results,
            qa_status,
            qa_answer,
            citation_results,
            chunk_selector,
            current_chunk_markdown,
            export_status,
            export_file,
        ],
        show_api=False,
    )

    export_qa_button.click(
        fn=export_qa,
        inputs=[current_bundle_state, qa_result_state],
        outputs=[
            selected_video_state,
            current_bundle_state,
            summary_card,
            key_info,
            artifact_paths,
            artifact_downloads,
            display_title_input,
            tags_input,
            notes_input,
            starred_checkbox,
            organize_status,
            saved_exports,
            saved_export_downloads,
            search_status,
            search_results,
            qa_status,
            qa_answer,
            citation_results,
            chunk_selector,
            current_chunk_markdown,
            export_status,
            export_file,
        ],
        show_api=False,
    )

    export_summary_button.click(
        fn=export_summary,
        inputs=[current_bundle_state],
        outputs=[
            selected_video_state,
            current_bundle_state,
            summary_card,
            key_info,
            artifact_paths,
            artifact_downloads,
            display_title_input,
            tags_input,
            notes_input,
            starred_checkbox,
            organize_status,
            saved_exports,
            saved_export_downloads,
            search_status,
            search_results,
            qa_status,
            qa_answer,
            citation_results,
            chunk_selector,
            current_chunk_markdown,
            export_status,
            export_file,
        ],
        show_api=False,
    )

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
            title_filter,
            starred_filter,
            sort_order,
            filtered_records_state,
            library_overview,
            language_filter,
            library_selector,
            library_search_status,
            library_search_results,
            library_search_results_state,
            selected_video_state,
            current_bundle_state,
            summary_card,
            key_info,
            artifact_paths,
            artifact_downloads,
            display_title_input,
            tags_input,
            notes_input,
            starred_checkbox,
            organize_status,
            saved_exports,
            saved_export_downloads,
            search_status,
            search_results,
            qa_status,
            qa_answer,
            citation_results,
            chunk_selector,
            current_chunk_markdown,
            export_status,
            export_file,
        ],
        show_progress="full",
        show_api=False,
    )

    clear_button.click(
        fn=lambda: (
            "## 等待开始\n\n处理完成后，这里会提示你回到“个人视频库”继续整理、搜索和提问。",
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


if __name__ == "__main__":
    demo.launch(
        server_name=DEFAULT_HOST,
        server_port=DEFAULT_PORT,
        show_api=False,
    )
