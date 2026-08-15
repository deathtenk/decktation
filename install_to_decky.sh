#!/bin/bash
# Fresh installation of Decktation to Decky
set -e

echo "=== Fresh Decktation Installation ==="
echo ""

# Determine plugin directory
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

echo "Source: $SOURCE_DIR"
echo "Target: $PLUGIN_DIR"
echo ""

# Remove old installation if exists
if [ -d "$PLUGIN_DIR" ]; then
    echo "Removing old installation..."
    rm -rf "$PLUGIN_DIR"
fi

# Create fresh plugin directory
echo "Creating plugin directory..."
mkdir -p "$PLUGIN_DIR"
mkdir -p "$PLUGIN_DIR/dist"
mkdir -p "$PLUGIN_DIR/bin"

# Copy essential files only
echo "Copying files..."
cp "$SOURCE_DIR/main.py" "$PLUGIN_DIR/"
cp "$SOURCE_DIR/telemetry.py" "$PLUGIN_DIR/"
cp "$SOURCE_DIR/convert_wow_context.py" "$PLUGIN_DIR/"
cp "$SOURCE_DIR/defaults/game_presets.json" "$PLUGIN_DIR/"
cp "$SOURCE_DIR/defaults/channel_languages.json" "$PLUGIN_DIR/"
cp "$SOURCE_DIR/package.json" "$PLUGIN_DIR/"
cp "$SOURCE_DIR/plugin.json" "$PLUGIN_DIR/"
cp "$SOURCE_DIR/runtime_client.py" "$PLUGIN_DIR/"

# Copy built frontend
if [ ! -f "$SOURCE_DIR/dist/index.js" ]; then
    echo "Building frontend..."
    cd "$SOURCE_DIR"
    npm run build
    cd - > /dev/null
fi
cp "$SOURCE_DIR/dist/index.js" "$PLUGIN_DIR/dist/"

# Copy WoW addon if exists
if [ -d "$SOURCE_DIR/WowAddon" ]; then
    echo "Copying WoW addon..."
    cp -r "$SOURCE_DIR/WowAddon" "$PLUGIN_DIR/"
fi

# Build or copy the packaged runtime artifact
if [ ! -x "$SOURCE_DIR/backend/out/decktation-runtime" ]; then
    echo "Building packaged runtime..."
    make -C "$SOURCE_DIR" runtime-build
fi

cp "$SOURCE_DIR/backend/out/decktation-runtime" "$PLUGIN_DIR/bin/"
if [ -d "$SOURCE_DIR/backend/out/licenses" ]; then
    mkdir -p "$PLUGIN_DIR/bin/licenses"
    cp -r "$SOURCE_DIR/backend/out/licenses/." "$PLUGIN_DIR/bin/licenses/"
fi

echo "✓ Files copied"
echo ""

# Set permissions
echo "Setting permissions..."
chmod 644 "$PLUGIN_DIR/main.py"
chmod 644 "$PLUGIN_DIR/telemetry.py"
chmod 644 "$PLUGIN_DIR/convert_wow_context.py"
chmod 644 "$PLUGIN_DIR/runtime_client.py"
chmod 755 "$PLUGIN_DIR/bin/decktation-runtime"

echo "✓ Permissions set"
echo ""

# Verify installation
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
