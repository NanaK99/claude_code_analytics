#!/usr/bin/env bash
set -euo pipefail

ENV_NAME="${CONDA_ENV_NAME:-provectus_task}"
API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8000}"
STREAMLIT_HOST="${STREAMLIT_HOST:-127.0.0.1}"
STREAMLIT_PORT="${STREAMLIT_PORT:-8501}"

if [[ -n "${CONDA_EXE:-}" && -x "${CONDA_EXE}" ]]; then
  CONDA_CMD="${CONDA_EXE}"
elif command -v conda >/dev/null 2>&1; then
  CONDA_CMD="$(command -v conda)"
else
  echo "Could not find conda. Set CONDA_EXE or add conda to PATH." >&2
  exit 1
fi

api_pid=""
streamlit_pid=""

cleanup() {
  local exit_code=$?

  if [[ -n "${streamlit_pid}" ]] && kill -0 "${streamlit_pid}" >/dev/null 2>&1; then
    kill "${streamlit_pid}" >/dev/null 2>&1 || true
  fi

  if [[ -n "${api_pid}" ]] && kill -0 "${api_pid}" >/dev/null 2>&1; then
    kill "${api_pid}" >/dev/null 2>&1 || true
  fi

  wait >/dev/null 2>&1 || true
  exit "${exit_code}"
}

trap cleanup EXIT INT TERM

# Load .env if present
if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

echo "Starting FastAPI on http://${API_HOST}:${API_PORT}"
"${CONDA_CMD}" run -n "${ENV_NAME}" uvicorn api:app --reload --host "${API_HOST}" --port "${API_PORT}" &
api_pid=$!

echo "Starting Streamlit on http://${STREAMLIT_HOST}:${STREAMLIT_PORT}"
"${CONDA_CMD}" run -n "${ENV_NAME}" streamlit run app.py --server.address "${STREAMLIT_HOST}" --server.port "${STREAMLIT_PORT}" &
streamlit_pid=$!

# wait -n is bash 4.3+ only; macOS ships bash 3.2 — poll both PIDs instead
while kill -0 "${api_pid}" 2>/dev/null && kill -0 "${streamlit_pid}" 2>/dev/null; do
  sleep 1
done
