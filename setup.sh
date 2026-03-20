#!/usr/bin/env bash
set -e

echo "=== UAE Turtle Trader — one-time setup ==="

# Require Python 3.11+
python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
required="3.11"
if [[ "$(printf '%s\n' "$required" "$python_version" | sort -V | head -n1)" != "$required" ]]; then
    echo "ERROR: Python $required+ required (found $python_version)" >&2
    exit 1
fi

echo "Python $python_version — OK"

# Install Python dependencies
pip install --upgrade pip -q
pip install -r requirements.txt

# Install Playwright Chromium browser
playwright install chromium

# Create data directory
mkdir -p data/history

echo ""
echo "Setup complete. Run the scanner with:"
echo "  python scan.py"
