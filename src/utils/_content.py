"""Anthropic response content helpers."""
from typing import Any, List


def extract_text(content: List[Any]) -> str:
    """Extract text from the first TextBlock, skipping ThinkingBlock etc."""
    for block in content or []:
        if hasattr(block, "text"):
            return block.text
    return ""
