#!/usr/bin/env bash
# build_macos.sh — Build, sign, and notarize SAMPSON.app
#
# Required environment variables for notarization:
#   APPLE_CODESIGN_IDENTITY  — e.g. "Developer ID Application: Your Name (TEAMID)"
#   APPLE_ID                 — Apple ID email used for notarization
#   APPLE_APP_PASSWORD       — App-specific password from appleid.apple.com
#   APPLE_TEAM_ID            — 10-character team ID (same as in parens above)
#
# If APPLE_CODESIGN_IDENTITY is unset, ad-hoc signing is used and notarization
# is skipped (good for local test builds).
#
# Usage:
#   bash build_macos.sh               # ad-hoc sign, no notarization
#   APPLE_CODESIGN_IDENTITY="Developer ID Application: ..." \
#   APPLE_ID="you@example.com" \
#   APPLE_APP_PASSWORD="xxxx-xxxx-xxxx-xxxx" \
#   APPLE_TEAM_ID="XXXXXXXXXX" \
#   bash build_macos.sh               # Developer ID sign + notarize

set -e

# Export for PyInstaller spec to read
export APPLE_CODESIGN_IDENTITY="${APPLE_CODESIGN_IDENTITY:--}"
CODESIGN_ID="$APPLE_CODESIGN_IDENTITY"
NOTARIZE=false
if [ "$CODESIGN_ID" != "-" ] && [ -n "$APPLE_ID" ] && [ -n "$APPLE_APP_PASSWORD" ] && [ -n "$APPLE_TEAM_ID" ]; then
    NOTARIZE=true
fi

echo "=== Building SAMPSON.app ==="
echo "Signing identity: ${CODESIGN_ID:0:60}..."
echo "Notarize: $NOTARIZE"

# Verify entitlements file exists (required for hardened runtime)
if [ ! -f "entitlements.plist" ]; then
    echo "ERROR: entitlements.plist not found. This file is required for code signing."
    exit 1
fi

# ── 1. Pre-download static-ffmpeg binaries (cached after first run) ────────────
echo ""
echo "[ 1/7 ] Pre-fetching ffmpeg binaries..."
.venv/bin/python3 -c "import static_ffmpeg; static_ffmpeg.add_paths()"

# ── 2. PyInstaller build ───────────────────────────────────────────────────────
echo ""
echo "[ 2/7 ] Running PyInstaller..."
.venv/bin/pyinstaller SAMPSON_mac.spec --clean -y

# ── 3. Clean up non-runtime Tcl/Tk data ───────────────────────────────────────
echo ""
echo "[ 3/7 ] Cleaning Tcl/Tk extras..."
TCL_DATA="dist/SAMPSON.app/Contents/Resources/_tcl_data"
if [ -d "$TCL_DATA" ]; then
    rm -rf "$TCL_DATA/msgs"
    rm -rf "$TCL_DATA/opt"[0-9]*       # Tcl opt package (version-numbered dir)
    rm -rf "$TCL_DATA/cookiejar"[0-9]* # Tcl cookiejar package
    rm -rf "$TCL_DATA/http"[0-9]*
    rm -rf "$TCL_DATA/tcltest"[0-9]*
    KEEP="ascii.enc utf-8.enc iso8859-1.enc cp1252.enc"
    if [ -d "$TCL_DATA/encoding" ]; then
        for f in "$TCL_DATA/encoding"/*.enc; do
            base=$(basename "$f")
            if ! echo "$KEEP" | grep -qw "$base"; then rm "$f"; fi
        done
    fi
fi
# NOTE: Do NOT delete python3.X or tcl9 directories here.
# python3.X/lib-dynload/ is the runtime path PyInstaller's bootloader uses for
# stdlib extension modules (.so files). Deleting it causes "No module named _struct"
# crashes at launch. The individual .so signing in step 5 handles these files.
# tcl9/ is similarly needed at runtime for Tcl package resolution.

# ── 4. Fix Python.framework symlink structure ──────────────────────────────────
# PyInstaller creates Python.framework with flat binaries instead of versioned
# symlinks, causing codesign to report "bundle format is ambiguous".
echo ""
echo "[ 4/7 ] Fixing Python.framework structure..."
fix_python_framework() {
    local FW="$1"
    if [ ! -d "$FW" ]; then return; fi

    # Detect the Python version directory (e.g. 3.14)
    local PYVER
    PYVER=$(ls "$FW/Versions/" | grep -E '^[0-9]' | head -1)
    if [ -z "$PYVER" ]; then return; fi

    # Make Versions/Current a symlink to the versioned dir (PyInstaller makes it a copy)
    if [ -d "$FW/Versions/Current" ] && [ ! -L "$FW/Versions/Current" ]; then
        cp "$FW/Versions/Current/Python" "$FW/Versions/$PYVER/Python" 2>/dev/null || true
        rm -rf "$FW/Versions/Current"
        ln -s "$PYVER" "$FW/Versions/Current"
    fi

    # Replace flat Python binary at root with symlink (the only change codesign requires)
    if [ -f "$FW/Python" ] && [ ! -L "$FW/Python" ]; then
        rm "$FW/Python"
        ln -s "Versions/Current/Python" "$FW/Python"
    fi

    # Leave Resources as a flat directory — symlinking it can create dangling refs
    # if Versions/$PYVER/Resources doesn't exist, which Gatekeeper rejects.
    # Do NOT add a Headers symlink for the same reason.
}

fix_python_framework "dist/SAMPSON.app/Contents/Resources/Python.framework"
fix_python_framework "dist/SAMPSON.app/Contents/Frameworks/Python.framework"

# ── 5. Sign ────────────────────────────────────────────────────────────────────
# Must sign outside OneDrive to prevent OneDrive from re-adding xattrs mid-sign.
echo ""
echo "[ 5/7 ] Preparing and signing..."
TMPAPP="/tmp/SAMPSON_build_$$.app"

# Copy to /tmp and clean ALL xattrs (critical for clean signature)
ditto "dist/SAMPSON.app" "$TMPAPP"
echo "Cleaning extended attributes..."
find "$TMPAPP" -exec xattr -c {} \; 2>/dev/null || true

# Also strip any resource forks
find "$TMPAPP" -name "._*" -delete 2>/dev/null || true

# Verify the app is clean
XATTR_COUNT=$(find "$TMPAPP" -exec xattr -l {} \; 2>/dev/null | grep -c ": " || echo "0")
echo "Remaining xattrs: $XATTR_COUNT"

sign() {
    codesign --force --sign "$CODESIGN_ID" --options runtime --timestamp \
        --entitlements entitlements.plist "$@" 2>&1 \
        | grep -v "replacing existing signature" || true
}

# Sign all binaries: dylibs, .so, Python binaries
# Process deepest files first so parent directories can be signed last
find "$TMPAPP" -type f \( -name "*.dylib" -o -name "*.so" -o -name "Python" \) | \
    awk '{print gsub(/\//,"/",$0), $0}' | sort -rn | cut -d' ' -f2- | \
    while read f; do
        sign "$f"
    done

# Sign ffmpeg + ffprobe (bundled by static-ffmpeg)
find "$TMPAPP" -path "*/static_ffmpeg/bin/*" \( -name "ffmpeg" -o -name "ffprobe" \) | while read f; do
    sign "$f"
done

# Sign the main executable
sign "$TMPAPP/Contents/MacOS/SAMPSON"

# Sign Python.frameworks (both locations) and their Python binaries
for LOC in Resources Frameworks; do
    FW="$TMPAPP/Contents/$LOC/Python.framework"
    if [ -d "$FW" ]; then
        PYVER=$(ls "$FW/Versions/" 2>/dev/null | grep -E '^[0-9]' | head -1)
        if [ -n "$PYVER" ] && [ -f "$FW/Versions/$PYVER/Python" ]; then
            sign --identifier "org.python.python" "$FW/Versions/$PYVER/Python"
        fi
        sign --identifier "org.python.python" "$FW"
    fi
    # Also sign any top-level Python binary copy
    if [ -f "$TMPAPP/Contents/$LOC/Python" ]; then
        sign --identifier "org.python.python" "$TMPAPP/Contents/$LOC/Python"
    fi
done

# Sign the app bundle itself (deep sign)
sign "$TMPAPP"

# Final verification
echo "Verifying signature before notarization..."
codesign -vv --deep --strict "$TMPAPP" 2>&1 || echo "WARNING: Signature verification failed"
echo "App signed."

# ── 6. Notarize ────────────────────────────────────────────────────────────────
if [ "$NOTARIZE" = true ]; then
    echo ""
    echo "[ 6/7 ] Notarizing..."
    ZIPPATH="/tmp/SAMPSON_notarize_$$.zip"
    ditto -c -k --keepParent "$TMPAPP" "$ZIPPATH"

    xcrun notarytool submit "$ZIPPATH" \
        --apple-id "$APPLE_ID" \
        --password "$APPLE_APP_PASSWORD" \
        --team-id "$APPLE_TEAM_ID" \
        --wait

    rm "$ZIPPATH"

    echo "Stapling notarization ticket..."
    xcrun stapler staple "$TMPAPP"

    echo "Verifying Gatekeeper acceptance..."
    spctl --assess --type execute --verbose "$TMPAPP" || \
        echo "WARNING: spctl rejected — check for dangling symlinks if this persists"
else
    echo ""
    echo "[ 6/7 ] Skipping notarization (no credentials provided)."
fi

# ── 7. Zip for distribution + copy signed app back to dist ────────────────────
# CRITICAL: OneDrive in dist/ injects xattrs that BREAK the code signature.
# We create the distribution zip in /tmp (clean), then copy the app back.
echo ""
echo "[ 7/7 ] Creating distribution zip (in /tmp to avoid OneDrive xattrs)..."
VERSION=$(grep 'CFBundleShortVersionString' SAMPSON_mac.spec | grep -o '[0-9]\+\.[0-9]\+\.[0-9]\+' | head -1)
ZIPPATH="$(pwd)/dist/SAMPSON_mac_v${VERSION}.zip"

# Aggressively clean ALL xattrs before zipping - this is critical!
# Any xattrs in the zip will invalidate the signature when extracted
find "$TMPAPP" -exec xattr -c {} \; 2>/dev/null || true
find "$TMPAPP" -name "._*" -delete 2>/dev/null || true
find "$TMPAPP" -name ".DS_Store" -delete 2>/dev/null || true

# Rename the app to SAMPSON.app for distribution
FINAL_APP="/tmp/SAMPSON.app"
rm -rf "$FINAL_APP"
ditto --noqtn --noacl --norsrc "$TMPAPP" "$FINAL_APP"

# Create zip using ditto with flags to avoid metadata
cd /tmp
rm -f "SAMPSON_dist_$$.zip"
ditto -c -k --keepParent --noqtn --noacl --norsrc "SAMPSON.app" "SAMPSON_dist_$$.zip"
rm -rf "$FINAL_APP"
cd - > /dev/null

# Move zip to dist
TMPZIP="/tmp/SAMPSON_dist_$$.zip"
if [ -f "$TMPZIP" ]; then
    mv "$TMPZIP" "$ZIPPATH"
    echo "Distribution zip: $ZIPPATH ($(du -sh "$ZIPPATH" | cut -f1))"
else
    echo "ERROR: Failed to create zip"
    exit 1
fi

# Copy app back to dist for local testing
# Note: OneDrive will add xattrs after copy, making signature invalid locally
# The zip file is the only clean distribution artifact
echo "Copying signed app to dist/ (for local testing only)..."
rm -rf "dist/SAMPSON.app"
ditto --noqtn --noacl --norsrc "$TMPAPP" "dist/SAMPSON.app"
rm -rf "$TMPAPP"

echo ""
echo "Done: dist/SAMPSON.app ($(du -sh dist/SAMPSON.app | cut -f1))"
echo ""
echo "Upload dist/SAMPSON_mac_v${VERSION}.zip to the GitHub release."
echo "Do NOT zip dist/SAMPSON.app — OneDrive will have corrupted its signature by then."
