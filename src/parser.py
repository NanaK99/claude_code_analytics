from typing import Optional, Tuple

_DISPATCH = {
    "claude_code.user_prompt":   "_parse_user_prompt",
    "claude_code.api_request":   "_parse_api_request",
    "claude_code.tool_decision": "_parse_tool_decision",
    "claude_code.tool_result":   "_parse_tool_result",
    "claude_code.api_error":     "_parse_api_error",
}


def parse_event(
    body: str, attrs: dict, line_num: int, event_idx: int
) -> Optional[Tuple[str, dict]]:
    """
    Parse a single telemetry event.
    Returns (table_name, row_dict) or None if the event type is unknown.
    Raises ValueError with location info if a required field is missing or invalid.
    """
    handler_name = _DISPATCH.get(body)
    if handler_name is None:
        return None
    try:
        return globals()[handler_name](attrs)
    except (KeyError, ValueError) as exc:
        raise ValueError(
            f"Line {line_num} (event index {event_idx}): "
            f"missing or invalid field in '{body}': {exc}"
        ) from exc


def _base(attrs: dict) -> dict:
    return {
        "session_id":    attrs["session.id"],
        "user_email":    attrs["user.email"],
        "timestamp":     attrs["event.timestamp"],
        "terminal_type": attrs.get("terminal.type"),
    }


def _parse_user_prompt(attrs: dict) -> Tuple[str, dict]:
    row = _base(attrs)
    row["prompt_length"] = int(attrs["prompt_length"])
    return "user_prompts", row


def _parse_api_request(attrs: dict) -> Tuple[str, dict]:
    row = _base(attrs)
    row.update({
        "model":                attrs["model"],
        "input_tokens":         int(attrs["input_tokens"]),
        "output_tokens":        int(attrs["output_tokens"]),
        "cache_read_tokens":    int(attrs["cache_read_tokens"]),
        "cache_creation_tokens": int(attrs["cache_creation_tokens"]),
        "cost_usd":             float(attrs["cost_usd"]),
        "duration_ms":          int(attrs["duration_ms"]),
    })
    return "api_requests", row


def _parse_tool_decision(attrs: dict) -> Tuple[str, dict]:
    row = _base(attrs)
    row.update({
        "tool_name": attrs["tool_name"],
        "decision":  attrs["decision"],
        "source":    attrs["source"],
    })
    return "tool_decisions", row


def _parse_tool_result(attrs: dict) -> Tuple[str, dict]:
    row = _base(attrs)
    row.update({
        "tool_name":        attrs["tool_name"],
        "decision_type":    attrs["decision_type"],
        "decision_source":  attrs["decision_source"],
        "success":          attrs["success"] == "true",
        "duration_ms":      int(attrs["duration_ms"]),
        "result_size_bytes": int(attrs["tool_result_size_bytes"])
                             if "tool_result_size_bytes" in attrs else None,
    })
    return "tool_results", row


def _parse_api_error(attrs: dict) -> Tuple[str, dict]:
    row = _base(attrs)
    row.update({
        "model":       attrs["model"],
        "error":       attrs["error"],
        "status_code": attrs["status_code"],
        "attempt":     int(attrs["attempt"]),
        "duration_ms": int(attrs["duration_ms"]),
    })
    return "api_errors", row
