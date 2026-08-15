#!/bin/bash
set -euo pipefail

echo "=== Fresh Decktation Installation ==="
echo ""

if [ -d ~/homebrew/plugins ]; then
    PLUGINS_DIR=~/homebrew/plugins
elif [ -d ~/.local/share/decky/plugins ]; then
    PLUGINS_DIR=~/.local/share/decky/plugins
else
    echo "Error: Cannot find Decky plugins directory!"
    exit 1
fi

PLUGIN_DIR="$PLUGINS_DIR/decktation"
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
TMP_DIR="$(mktemp -d)"
ZIP_URL="${DECKTATION_ZIP_URL:-https://github.com/deathtenk/decktation/releases/latest/download/decktation.zip}"
LOCAL_ZIP="${DECKTATION_ZIP_PATH:-$SOURCE_DIR/build-output/decktation.zip}"
ZIP_PATH="$TMP_DIR/decktation.zip"

cleanup() {
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT

echo "Source: $SOURCE_DIR"
echo "Target: $PLUGIN_DIR"
echo ""

if [ -d "$PLUGIN_DIR" ]; then
    echo "Removing old installation..."
    rm -rf "$PLUGIN_DIR"
fi

if [ -f "$LOCAL_ZIP" ]; then
    echo "Using local packaged ZIP: $LOCAL_ZIP"
    cp "$LOCAL_ZIP" "$ZIP_PATH"
else
    echo "Downloading packaged ZIP:"
    echo "  $ZIP_URL"
    curl -fL "$ZIP_URL" -o "$ZIP_PATH"
fi

echo "Extracting packaged ZIP..."
unzip -q "$ZIP_PATH" -d "$TMP_DIR/unpacked"

EXTRACTED_PLUGIN_DIR="$TMP_DIR/unpacked/decktation"
if [ ! -d "$EXTRACTED_PLUGIN_DIR" ]; then
    echo "Error: packaged ZIP did not contain decktation/ at the archive root"
    exit 1
fi

echo "Installing packaged plugin files..."
mkdir -p "$PLUGIN_DIR"
cp -R "$EXTRACTED_PLUGIN_DIR"/. "$PLUGIN_DIR/"

echo "✓ Files copied"
echo ""

echo "Setting permissions..."
find "$PLUGIN_DIR" -type f -name '*.py' -exec chmod 644 {} +
if [ -f "$PLUGIN_DIR/bin/decktation-runtime" ]; then
    chmod 755 "$PLUGIN_DIR/bin/decktation-runtime"
fi
echo "✓ Permissions set"
echo ""

echo "Verifying installation..."
if [ -x "$PLUGIN_DIR/bin/decktation-runtime" ]; then
    echo "✓ runtime executable installed"
else
    echo "✗ runtime executable missing!"
fi

if [ -f "$PLUGIN_DIR/dist/index.js" ]; then
    echo "✓ Frontend built"
else
    echo "✗ Frontend missing!"
fi

if [ -f "$PLUGIN_DIR/plugin.json" ]; then
    echo "✓ Plugin manifest installed"
else
    echo "✗ Plugin manifest missing!"
fi

echo ""
echo "========================================="
echo "Installation complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Restart Decky Loader:"
echo "   systemctl --user restart plugin_loader"
echo ""
echo "2. Wait ~10 seconds for Decky to start"
echo ""
echo "3. Check logs:"
echo "   tail -f /tmp/decktation.log"
echo ""
echo "4. Open Quick Access Menu (... button)"
echo "   Navigate to Decktation plugin"
echo ""
echo "You should see button configuration dropdowns!"
echo ""
