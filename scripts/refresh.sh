#!/usr/bin/env bash
# Refresh the contribution snake and the stats card under it in one go.
# Needs: python3 and `pip install fonttools uharfbuzz brotli`. Then commit and push the changed files.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/make_snake.py "$@"   # fetches your contribution calendar; writes the snakes + assets/data/activity.json
python3 scripts/build_assets.py      # rebuilds stats.svg (and the rest of the artwork) from that data
