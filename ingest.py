import json
import os
import duckdb
import pandas as pd
from tqdm import tqdm
from src.schema import init_db
from src.parser import parse_event

CHUNK_SIZE = 10_000
TELEMETRY_PATH = "data_generation/output/telemetry_logs.jsonl"
EMPLOYEES_PATH = "data_generation/output/employees.csv"
DB_PATH = "db/analytics.duckdb"

_TABLES = ["user_prompts", "api_requests", "tool_decisions", "tool_results", "api_errors"]
_ALLOWED_TABLES = set(_TABLES)


def _flush(conn, table_name: str, rows: list, col_order: list) -> None:
    if table_name not in _ALLOWED_TABLES:
        raise ValueError(f"Unknown table: {table_name!r}")
    if not rows:
        return
    df = pd.DataFrame(rows)
    col_list = ", ".join(col_order)
    conn.execute(f"INSERT INTO {table_name} SELECT {col_list} FROM df")


def run_ingest(
    conn,
    telemetry_path: str = TELEMETRY_PATH,
    employees_path: str = EMPLOYEES_PATH,
) -> dict:
    # Load employees — DuckDB references the local `emp_df` variable by name
    emp_df = pd.read_csv(employees_path)
    conn.execute("INSERT INTO employees SELECT email, full_name, practice, level, location FROM emp_df")

    _col_order = {}
    for table in _TABLES:
        cols = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = ? ORDER BY ordinal_position",
            [table]
        ).fetchall()
        _col_order[table] = [c[0] for c in cols]

    buffers = {t: [] for t in _TABLES}
    counts = {"ingested": 0, "malformed": 0, "missing_fields": 0, "unknown_types": 0}
    error_lines: dict = {"malformed": [], "missing_fields": [], "unknown_types": []}

    with open(telemetry_path) as f:
        for line_num, line in enumerate(tqdm(f, desc="Ingesting batches"), 1):
            try:
                batch = json.loads(line)
            except json.JSONDecodeError:
                counts["malformed"] += 1
                error_lines["malformed"].append(str(line_num))
                continue

            for event_idx, log_event in enumerate(batch.get("logEvents", [])):
                try:
                    event = json.loads(log_event["message"])
                except (json.JSONDecodeError, KeyError):
                    counts["missing_fields"] += 1
                    error_lines["missing_fields"].append(
                        f"Line {line_num} (event index {event_idx}): failed to parse message JSON"
                    )
                    continue

                body = event.get("body")
                attrs = event.get("attributes")
                if not body or not attrs:
                    counts["missing_fields"] += 1
                    error_lines["missing_fields"].append(
                        f"Line {line_num} (event index {event_idx}): missing 'body' or 'attributes'"
                    )
                    continue

                try:
                    result = parse_event(body, attrs, line_num, event_idx)
                except ValueError as exc:
                    counts["missing_fields"] += 1
                    error_lines["missing_fields"].append(str(exc))
                    continue

                if result is None:
                    counts["unknown_types"] += 1
                    error_lines["unknown_types"].append(
                        f"Line {line_num} (event index {event_idx}): unknown type '{body}'"
                    )
                    continue

                table_name, row = result
                buffers[table_name].append(row)
                counts["ingested"] += 1

                if len(buffers[table_name]) >= CHUNK_SIZE:
                    _flush(conn, table_name, buffers[table_name], _col_order[table_name])
                    buffers[table_name] = []

    for table_name, rows in buffers.items():
        _flush(conn, table_name, rows, _col_order[table_name])

    _print_summary(counts, error_lines)
    return counts


def _print_summary(counts: dict, error_lines: dict) -> None:
    total_skipped = sum(counts[k] for k in ("malformed", "missing_fields", "unknown_types"))

    def fmt(key, label):
        lines = error_lines[key]
        suffix = f" (lines: {', '.join(lines[:10])}{'...' if len(lines) > 10 else ''})" if lines else ""
        return f"  {label:<20} {counts[key]:>6}{suffix}"

    print("\nIngestion complete.")
    print(f"  {'Ingested:':<20} {counts['ingested']:>6,} events")
    print(fmt("malformed", "Malformed JSON:"))
    print(fmt("missing_fields", "Missing fields:"))
    print(fmt("unknown_types", "Unknown types:"))
    print(f"  {'Total skipped:':<20} {total_skipped:>6}")


if __name__ == "__main__":
    os.makedirs("db", exist_ok=True)
    conn = duckdb.connect(DB_PATH)
    init_db(conn)
    run_ingest(conn)
    conn.close()
