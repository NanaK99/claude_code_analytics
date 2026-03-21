import pytest
from src.parser import parse_event

BASE_ATTRS = {
    "session.id": "sess-abc",
    "user.email": "alice@example.com",
    "event.timestamp": "2025-12-03T00:06:00.000Z",
    "terminal.type": "vscode",
}

def make_attrs(**extra):
    return {**BASE_ATTRS, **extra}


def test_parse_user_prompt_fields_and_type_cast():
    attrs = make_attrs(prompt_length="420")
    table, row = parse_event("claude_code.user_prompt", attrs, 1, 0)
    assert table == "user_prompts"
    assert row["session_id"] == "sess-abc"
    assert row["user_email"] == "alice@example.com"
    assert row["prompt_length"] == 420
    assert row["terminal_type"] == "vscode"


def test_parse_api_request_casts_numerics():
    attrs = make_attrs(
        model="claude-sonnet-4-6",
        input_tokens="0", output_tokens="939",
        cache_read_tokens="55024", cache_creation_tokens="0",
        cost_usd="0.005496", duration_ms="9078",
    )
    table, row = parse_event("claude_code.api_request", attrs, 1, 0)
    assert table == "api_requests"
    assert row["output_tokens"] == 939
    assert isinstance(row["cost_usd"], float)
    assert row["duration_ms"] == 9078


def test_parse_tool_decision():
    attrs = make_attrs(tool_name="Edit", decision="reject", source="user_reject")
    table, row = parse_event("claude_code.tool_decision", attrs, 1, 0)
    assert table == "tool_decisions"
    assert row["tool_name"] == "Edit"
    assert row["decision"] == "reject"
    assert row["source"] == "user_reject"


def test_parse_tool_result_with_optional_size():
    attrs = make_attrs(
        tool_name="Read", decision_type="accept", decision_source="config",
        success="true", duration_ms="61", tool_result_size_bytes="1024",
    )
    table, row = parse_event("claude_code.tool_result", attrs, 1, 0)
    assert table == "tool_results"
    assert row["success"] is True
    assert row["result_size_bytes"] == 1024


def test_parse_tool_result_without_optional_size():
    attrs = make_attrs(
        tool_name="Bash", decision_type="accept", decision_source="config",
        success="false", duration_ms="200",
    )
    _, row = parse_event("claude_code.tool_result", attrs, 1, 0)
    assert row["result_size_bytes"] is None
    assert row["success"] is False


def test_parse_api_error():
    attrs = make_attrs(
        model="claude-opus-4-5-20251101",
        error="OAuth token has expired.",
        status_code="401", attempt="2", duration_ms="943",
    )
    table, row = parse_event("claude_code.api_error", attrs, 1, 0)
    assert table == "api_errors"
    assert row["status_code"] == "401"
    assert row["attempt"] == 2


def test_unknown_event_type_returns_none():
    result = parse_event("claude_code.future_event", {}, 1, 0)
    assert result is None


def test_missing_required_field_raises_value_error():
    # prompt_length is missing — should raise ValueError with location info
    attrs = make_attrs()  # no prompt_length
    with pytest.raises(ValueError, match="Line 5 \\(event index 2\\)"):
        parse_event("claude_code.user_prompt", attrs, 5, 2)
