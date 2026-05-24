"""文件批量转 Markdown — 用 markitdown 包装，给 Agent 注入参考文件内容"""

from __future__ import annotations

from pathlib import Path

import structlog

logger = structlog.get_logger()

_SUPPORTED_EXT = {
    ".pdf", ".docx", ".pptx", ".xlsx", ".xls",
    ".csv", ".html", ".htm", ".epub", ".msg",
    ".json", ".xml", ".txt", ".md", ".ipynb", ".zip",
}


def extract_files_to_markdown(
    files: list[str],
    max_chars_per_file: int = 20_000,
) -> str:
    """把 files 列表批量转 Markdown，拼成单一字符串。

    失败文件 skip + warning，不抛异常。
    单文件超过 max_chars_per_file 截断并附 [...truncated] 标记。
    跳过非白名单扩展名（含图片/音频，由 vision API 路径处理）。
    """
    if not files:
        return ""

    try:
        from markitdown import MarkItDown
    except ImportError:
        logger.warning("markitdown_not_installed")
        return ""

    md = MarkItDown()
    sections: list[str] = []

    for path_str in files:
        path = Path(path_str)
        ext = path.suffix.lower()

        if ext not in _SUPPORTED_EXT:
            logger.info("file_extraction_skip_unsupported", path=path_str, ext=ext)
            continue

        if not path.exists():
            logger.warning("file_extraction_skip_missing", path=path_str)
            continue

        try:
            result = md.convert(str(path))
            text = result.text_content or ""
        except Exception as e:
            logger.warning("file_extraction_failed", path=path_str, error=str(e))
            continue

        if len(text) > max_chars_per_file:
            text = text[:max_chars_per_file] + "\n\n[...truncated]"

        sections.append(f"## {path.name}\n\n{text}")
        logger.info("file_extraction_succeeded", path=path_str, chars=len(text))

    return "\n\n".join(sections)
