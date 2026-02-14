#!/usr/bin/env sh
set -e

case "${SERVICE}" in
  api)
    exec uv run --no-project uvicorn app.main:app --host 0.0.0.0 --port 8000
    ;;
  ui)
    exec uv run --no-project streamlit run ui.py --server.address 0.0.0.0 --server.port 8501
    ;;
  *)
    echo "ERROR: SERVICE must be set to 'api' or 'ui'" >&2
    exit 1
    ;;
 esac