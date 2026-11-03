#!/usr/bin/env bash
# Frostbite verification loop. Usage: verify/run.sh [--self-test] [--only 'G2.*'] [--no-qmk]
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UV="${UV:-$HOME/.local/bin/uv}"
export PATH="$HOME/.local/bin:$HOME/Library/Application Support/qmk/bin:$PATH"
export UV_PROJECT_ENVIRONMENT="$HERE/.venv"
export PYTHONDONTWRITEBYTECODE=1
cd "$HERE"
exec "$UV" run --frozen --python 3.12 --project "$HERE" python -m fbverify "$@"
