#!/bin/zsh
# Запуск существующего FastAPI-сервера и интерфейса на macOS.
set -eu
cd -- "$(dirname -- "$0")"

if [[ ! -x .venv/bin/python ]]; then
  navigator_python=''
  for navigator_candidate in python3.13 python3.14 python3.12 python3.11 python3.10 python3; do
    if command -v "$navigator_candidate" >/dev/null 2>&1 && "$navigator_candidate" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
      navigator_python="$navigator_candidate"
      break
    fi
  done
  if [[ -z "$navigator_python" ]]; then
    print 'Для запуска нужен Python 3.10 или новее.'
    exit 1
  fi
  "$navigator_python" -m venv .venv
fi
navigator_python="$PWD/.venv/bin/python"
if ! "$navigator_python" -c 'import fastapi, uvicorn, httpx, pymorphy3, sqlalchemy, redis, psycopg, email_validator' 2>/dev/null; then
  "$navigator_python" -m pip install -r requirements.txt
fi

navigator_ready() {
  "$navigator_python" - <<'PY'
import json
import sys
import urllib.request
try:
    with urllib.request.urlopen('http://localhost:4173/openapi.json', timeout=0.5) as response:
        schema = json.load(response)
    sys.exit(0 if 'post' in schema.get('paths', {}).get('/api/search', {}) else 1)
except Exception:
    sys.exit(1)
PY
}

print 'Право рядом: http://localhost:4173'
if navigator_ready; then
  if [[ "${1:-}" != '--no-browser' ]]; then open 'http://localhost:4173'; fi
  exit 0
fi

if [[ "${1:-}" != '--no-browser' ]]; then
  (
    for navigator_attempt in {1..60}; do
      if navigator_ready; then open 'http://localhost:4173'; exit 0; fi
      sleep 0.2
    done
  ) &
  navigator_opener_pid=$!
  trap 'kill "$navigator_opener_pid" 2>/dev/null || true' EXIT
fi

"$navigator_python" -m uvicorn app.server:app --host 127.0.0.1 --port 4173
