"""Sanitize Claude API messages to avoid `text content blocks must be non-empty`.

The Anthropic Messages API rejects requests when a `text` block has an empty
or whitespace-only `text` field. This module strips those blocks (and any
messages that end up with no content) before they are sent.

Typical usage:

    from anthropic import Anthropic
    from sanitize_messages import sanitize_messages

    client = Anthropic()
    resp = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        messages=sanitize_messages(history),
    )
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable


def _is_empty_text_block(block: Any) -> bool:
    if not isinstance(block, dict):
        return False
    if block.get("type") != "text":
        return False
    text = block.get("text")
    return not isinstance(text, str) or text.strip() == ""


def _sanitize_content(content: Any) -> Any:
    if isinstance(content, str):
        return content if content.strip() != "" else None

    if not isinstance(content, list):
        return content

    cleaned: list[Any] = []
    for block in content:
        if _is_empty_text_block(block):
            continue
        if isinstance(block, dict) and block.get("type") == "tool_result":
            inner = block.get("content")
            if isinstance(inner, list):
                inner_cleaned = [b for b in inner if not _is_empty_text_block(b)]
                block = {**block, "content": inner_cleaned or [{"type": "text", "text": " "}]}
            elif isinstance(inner, str) and inner.strip() == "":
                block = {**block, "content": " "}
        cleaned.append(block)

    return cleaned or None


def sanitize_messages(messages: Iterable[dict]) -> list[dict]:
    """Return a copy of ``messages`` with empty text blocks removed.

    - Drops `{"type": "text", "text": ""}` (and whitespace-only) blocks.
    - Drops messages whose content becomes empty after filtering.
    - Replaces empty `tool_result` content with a single space so the
      tool_use/tool_result pairing stays valid.
    """
    result: list[dict] = []
    for message in messages:
        msg = deepcopy(message)
        content = _sanitize_content(msg.get("content"))
        if content is None or (isinstance(content, list) and not content):
            continue
        msg["content"] = content
        result.append(msg)
    return result


if __name__ == "__main__":
    sample = [
        {"role": "user", "content": "안녕"},
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": ""},
                {"type": "tool_use", "id": "t1", "name": "search", "input": {}},
            ],
        },
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": ""},
            ],
        },
        {"role": "assistant", "content": [{"type": "text", "text": "   "}]},
    ]

    from json import dumps

    print(dumps(sanitize_messages(sample), ensure_ascii=False, indent=2))
