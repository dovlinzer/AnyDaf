#!/usr/bin/env bash
# Wrapper for upload_to_supabase.py — activates the venv automatically.
#
# Usage (same flags as the Python script):
#   ./run_upload.sh --sections
#   ./run_upload.sh --sections --tractates "Berakhot,Shabbat"
#   ./run_upload.sh --dir output/berakhot_11 --sections
#   ./run_upload.sh --dry-run --sections

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/venv"

if [[ ! -f "$VENV/bin/activate" ]]; then
    echo "ERROR: venv not found at $VENV"
    echo "Create it first:"
    echo "  cd $SCRIPT_DIR"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install openai requests python-dotenv"
    exit 1
fi

# shellcheck source=/dev/null
source "$VENV/bin/activate"

exec python "$SCRIPT_DIR/upload_to_supabase.py" "$@"
