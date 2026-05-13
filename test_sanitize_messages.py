"""Tests for sanitize_messages."""

from sanitize_messages import sanitize_messages


def test_drops_empty_text_block_keeps_tool_use():
    messages = [
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": ""},
                {"type": "tool_use", "id": "t1", "name": "search", "input": {}},
            ],
        }
    ]
    cleaned = sanitize_messages(messages)
    assert cleaned == [
        {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "t1", "name": "search", "input": {}},
            ],
        }
    ]


def test_drops_whitespace_only_text_block():
    messages = [{"role": "assistant", "content": [{"type": "text", "text": "   "}]}]
    assert sanitize_messages(messages) == []


def test_keeps_non_empty_text():
    messages = [{"role": "user", "content": [{"type": "text", "text": "안녕"}]}]
    assert sanitize_messages(messages) == messages


def test_string_content_passthrough():
    messages = [{"role": "user", "content": "hi"}]
    assert sanitize_messages(messages) == messages


def test_drops_message_with_empty_string_content():
    messages = [
        {"role": "user", "content": ""},
        {"role": "user", "content": "ok"},
    ]
    assert sanitize_messages(messages) == [{"role": "user", "content": "ok"}]


def test_tool_result_empty_content_gets_space():
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": ""},
            ],
        }
    ]
    cleaned = sanitize_messages(messages)
    assert cleaned[0]["content"][0]["content"] == " "


def test_tool_result_with_empty_inner_text_block():
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "t1",
                    "content": [{"type": "text", "text": ""}],
                },
            ],
        }
    ]
    cleaned = sanitize_messages(messages)
    inner = cleaned[0]["content"][0]["content"]
    assert inner == [{"type": "text", "text": " "}]


def test_does_not_mutate_input():
    messages = [
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": ""},
                {"type": "text", "text": "keep"},
            ],
        }
    ]
    snapshot = [dict(m) for m in messages]
    sanitize_messages(messages)
    assert messages == snapshot


if __name__ == "__main__":
    test_drops_empty_text_block_keeps_tool_use()
    test_drops_whitespace_only_text_block()
    test_keeps_non_empty_text()
    test_string_content_passthrough()
    test_drops_message_with_empty_string_content()
    test_tool_result_empty_content_gets_space()
    test_tool_result_with_empty_inner_text_block()
    test_does_not_mutate_input()
    print("all tests passed")
