#!/usr/bin/env bash

# ⚡ Naked Gemini TUI - Quick Launcher Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -d "$SCRIPT_DIR/env" ]; then
    echo "⚡ Sanal ortam (env) oluşturuluyor..."
    python3 -m venv "$SCRIPT_DIR/env"
    echo "📦 Bağımlılıklar yükleniyor..."
    "$SCRIPT_DIR/env/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"
fi

exec "$SCRIPT_DIR/env/bin/python" "$SCRIPT_DIR/gemini_tui.py" "$@"
