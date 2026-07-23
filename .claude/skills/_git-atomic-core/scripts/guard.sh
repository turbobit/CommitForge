#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if command -v python3 >/dev/null 2>&1; then
  exec python3 "$SCRIPT_DIR/guard.py" "$@"
elif command -v python >/dev/null 2>&1; then
  if python -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
    exec python "$SCRIPT_DIR/guard.py" "$@"
  fi
elif command -v py >/dev/null 2>&1; then
  exec py -3 "$SCRIPT_DIR/guard.py" "$@"
fi

printf '%s\n' '{"ok": false, "error": "Python 3.9 이상을 찾을 수 없습니다."}'
exit 127
