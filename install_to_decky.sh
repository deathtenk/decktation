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
CURRENT_USER="$(id -un)"
CURRENT_GROUP="$(id -gn)"
SUDO=""
PLUGIN_LOADER_STOPPED=""

cleanup() {
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT

need_sudo_for_plugins_dir() {
    [ ! -w "$PLUGINS_DIR" ] || { [ -e "$PLUGIN_DIR" ] && [ ! -w "$PLUGIN_DIR" ]; }
}

stop_plugin_loader() {
    if systemctl --user is-active --quiet plugin_loader 2>/dev/null; then
        systemctl --user stop plugin_loader
        PLUGIN_LOADER_STOPPED="user"
        return
    fi

    if command -v systemctl >/dev/null 2>&1 && [ -n "$SUDO" ] && $SUDO systemctl is-active --quiet plugin_loader 2>/dev/null; then
        $SUDO systemctl stop plugin_loader
        PLUGIN_LOADER_STOPPED="system"
    fi
}

start_plugin_loader() {
    case "$PLUGIN_LOADER_STOPPED" in
        user)
            systemctl --user start plugin_loader
            ;;
        system)
            $SUDO systemctl start plugin_loader
            ;;
    esac
}

echo "Source: $SOURCE_DIR"
echo "Target: $PLUGIN_DIR"
echo ""

if need_sudo_for_plugins_dir; then
    if ! command -v sudo >/dev/null 2>&1; then
        echo "Error: $PLUGIN_DIR is not writable and sudo is unavailable."
        exit 1
    fi
    SUDO="sudo"
    echo "Plugin directory is not writable; using sudo to normalize ownership..."
fi

stop_plugin_loader

if [ -d "$PLUGIN_DIR" ]; then
    echo "Removing old installation..."
    if [ -n "$SUDO" ]; then
        $SUDO rm -rf "$PLUGIN_DIR"
    else
        rm -rf "$PLUGIN_DIR"
    fi
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
if [ -n "$SUDO" ]; then
    $SUDO mkdir -p "$PLUGINS_DIR"
    $SUDO chown "$CURRENT_USER:$CURRENT_GROUP" "$PLUGINS_DIR"
fi
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
start_plugin_loader

echo "Next steps:"
echo ""
if [ "$PLUGIN_LOADER_STOPPED" = "user" ] || [ "$PLUGIN_LOADER_STOPPED" = "system" ]; then
    echo "1. Wait ~10 seconds for Decky Loader to start"
else
    echo "1. Restart Decky Loader if needed"
fi
echo ""
echo "2. Check logs:"
echo "   tail -f /tmp/decktation.log"
echo ""
echo "3. Open Quick Access Menu (... button)"
echo "   Navigate to Decktation plugin"
echo ""
echo "You should see button configuration dropdowns!"
echo ""
