#!/usr/bin/env bash
set -e
echo "Building SAMPSON.app..."

# Pre-download static-ffmpeg binaries (cached after first run)
python -c "import static_ffmpeg; static_ffmpeg.add_paths()"

pyinstaller SAMPSON_mac.spec --clean

echo "Done: dist/SAMPSON.app"
