#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ -d TheMatrix.app/Contents/MacOS/run ]]; then
  exec TheMatrix.app/Contents/MacOS/run "$@"
fi

python3 -m pip install -q -r requirements.txt
exec python3 main.py "$@"
