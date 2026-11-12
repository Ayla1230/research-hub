#!/usr/bin/env sh
# Research Hub — start from the repository root.  Usage: ./start.sh [--port 8770] [--demo] [--lang en]
cd "$(dirname "$0")" || exit 1
PY=$(command -v python3 || command -v python)
if [ -z "$PY" ]; then echo "Python 3.10+ is required: https://www.python.org/downloads/"; exit 1; fi
exec "$PY" -m research_hub serve "$@"
