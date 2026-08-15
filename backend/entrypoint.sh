#!/bin/sh
set -eu

cd /backend
mkdir -p out/licenses out/lib
cp /runtime-build/runtime/dist/decktation-runtime out/decktation-runtime
chmod 755 out/decktation-runtime
cp -L /usr/lib/libportaudio.so.2 out/lib/libportaudio.so.2
cp /ydotool-src/LICENSE out/licenses/ydotool-AGPL-3.0.txt
cp /usr/share/licenses/portaudio/LICENSE.txt out/licenses/portaudio-MIT.txt
