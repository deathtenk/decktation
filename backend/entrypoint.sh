#!/bin/sh
set -eu

cd /backend
mkdir -p out/licenses
cp /runtime-build/runtime/dist/decktation-runtime out/decktation-runtime
chmod 755 out/decktation-runtime
cp /ydotool-src/LICENSE out/licenses/ydotool-AGPL-3.0.txt
