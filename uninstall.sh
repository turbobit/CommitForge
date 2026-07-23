#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SCOPE="${1:-project}"
TARGET="${2:-$PWD}"

case "$SCOPE" in
  project)
    exec python3 "$SCRIPT_DIR/uninstall.py" --scope project --target "$TARGET"
    ;;
  global)
    exec python3 "$SCRIPT_DIR/uninstall.py" --scope global
    ;;
  dry-run-project)
    exec python3 "$SCRIPT_DIR/uninstall.py" --scope project --target "$TARGET" --dry-run
    ;;
  dry-run-global)
    exec python3 "$SCRIPT_DIR/uninstall.py" --scope global --dry-run
    ;;
  *)
    echo "사용법: $0 [project|global|dry-run-project|dry-run-global] [project-root]" >&2
    exit 2
    ;;
esac
