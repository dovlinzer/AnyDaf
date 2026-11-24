#!/bin/sh
# One-time (or after Homebrew upgrades Python): make AnyMishnahWeb/.venv with what build_site.py needs.
# Build with:  .venv/bin/python scripts/build_site.py
cd "$(dirname "$0")/.." || exit 1
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt && echo "ready: .venv/bin/python scripts/build_site.py"
