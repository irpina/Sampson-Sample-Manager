#!/usr/bin/env bash
set -e
echo "Building SAMPSON.app..."

# Pre-download static-ffmpeg binaries (cached after first run)
python -c "import static_ffmpeg; static_ffmpeg.add_paths()"

pyinstaller SAMPSON_mac.spec --clean

echo "Cleaning unused Tcl/Tk data files..."
TCL_DATA="dist/SAMPSON.app/Contents/Resources/_tcl_data"

if [ -d "$TCL_DATA" ]; then
    # Remove all language message catalogs (app is English-only)
    rm -rf "$TCL_DATA/msgs"
    
    # Remove all character encodings except the ones tkinter actually needs
    KEEP="ascii.enc utf-8.enc iso8859-1.enc cp1252.enc"
    if [ -d "$TCL_DATA/encoding" ]; then
        for f in "$TCL_DATA/encoding"/*.enc; do
            base=$(basename "$f")
            if ! echo "$KEEP" | grep -qw "$base"; then
                rm "$f"
            fi
        done
    fi
    
    # Remove optional Tcl packages (cookiejar, http) — SAMPSON doesn't use them
    rm -rf "$TCL_DATA/cookiejar"*
    rm -rf "$TCL_DATA/http"*
    rm -rf "$TCL_DATA/tcltest"*
fi

echo "Done: dist/SAMPSON.app ($(du -sh dist/SAMPSON.app | cut -f1))"
