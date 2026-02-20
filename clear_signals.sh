#!/bin/bash
# Clear signals.json with proper empty structure
# cBot expects a JSON object (not array)

SIGNALS_FILE="$HOME/GlitchMatrix/signals.json"

echo "{}" > "$SIGNALS_FILE"

echo "✅ Cleared signals.json (empty object)"
echo "📂 Path: $SIGNALS_FILE"
