#!/usr/bin/env bash
# notarize.sh — Notarize a pre-built SAMPSON.app
#
# Use this script to notarize an already-signed SAMPSON.app bundle.
# Useful for retrying failed notarization or notarizing a release build.
#
# Required environment variables:
#   APPLE_ID                 — Apple ID email used for notarization
#   APPLE_APP_PASSWORD       — App-specific password from appleid.apple.com
#   APPLE_TEAM_ID            — 10-character team ID
#
# Optional:
#   APPLE_CODESIGN_IDENTITY  — Re-sign before notarizing (defaults to ad-hoc "-")
#
# Usage:
#   APPLE_ID="you@example.com" \
#   APPLE_APP_PASSWORD="xxxx-xxxx-xxxx-xxxx" \
#   APPLE_TEAM_ID="XXXXXXXXXX" \
#   ./notarize.sh dist/SAMPSON.app

set -e

APP_PATH="${1:-dist/SAMPSON.app}"
CODESIGN_ID="${APPLE_CODESIGN_IDENTITY:--}"

# Validate arguments
if [ ! -d "$APP_PATH" ]; then
    echo "ERROR: App bundle not found: $APP_PATH"
    echo "Usage: $0 /path/to/SAMPSON.app"
    exit 1
fi

if [ -z "$APPLE_ID" ] || [ -z "$APPLE_APP_PASSWORD" ] || [ -z "$APPLE_TEAM_ID" ]; then
    echo "ERROR: Missing required environment variables."
    echo ""
    echo "Please set:"
    echo "  APPLE_ID             - Your Apple ID email"
    echo "  APPLE_APP_PASSWORD   - App-specific password from appleid.apple.com"
    echo "  APPLE_TEAM_ID        - Your 10-character Team ID"
    echo ""
    echo "Example:"
    echo '  APPLE_ID="you@example.com" \'
    echo '  APPLE_APP_PASSWORD="abcd-abcd-abcd-abcd" \'
    echo '  APPLE_TEAM_ID="A1B2C3D4E5" \'
    echo "  $0 $APP_PATH"
    exit 1
fi

# Resolve absolute path
ABS_APP_PATH="$(cd "$(dirname "$APP_PATH")" && pwd)/$(basename "$APP_PATH")"

echo "=== Notarizing SAMPSON.app ==="
echo "App path: $ABS_APP_PATH"
echo "Signing identity: ${CODESIGN_ID:0:60}..."

# Work in /tmp to avoid OneDrive xattr issues
TMPAPP="/tmp/SAMPSON_notarize_$$.app"
echo ""
echo "[1/5] Copying to /tmp (avoiding OneDrive xattrs)..."
ditto "$ABS_APP_PATH" "$TMPAPP"
xattr -cr "$TMPAPP" 2>/dev/null || true

# Re-sign if a Developer ID is provided
if [ "$CODESIGN_ID" != "-" ]; then
    echo ""
    echo "[2/5] Re-signing with Developer ID..."
    
    sign() {
        codesign --force --sign "$CODESIGN_ID" --options runtime --timestamp --entitlements entitlements.plist "$@" 2>&1 \
            | grep -v "replacing existing signature" || true
    }
    
    # Sign all binaries
    find "$TMPAPP" \( -name "*.dylib" -o -name "*.so" \) | while read f; do
        sign "$f"
    done
    
    find "$TMPAPP" -path "*/static_ffmpeg/bin/*" \( -name "ffmpeg" -o -name "ffprobe" \) | while read f; do
        sign "$f"
    done
    
    for LOC in Resources Frameworks; do
        FW="$TMPAPP/Contents/$LOC/Python.framework"
        if [ -d "$FW" ]; then
            PYVER=$(ls "$FW/Versions/" | grep -E '^[0-9]' | head -1)
            sign --identifier "org.python.python" "$FW/Versions/$PYVER/Python"
            sign --identifier "org.python.python" "$FW"
        fi
        if [ -f "$TMPAPP/Contents/$LOC/Python" ]; then
            sign --identifier "org.python.python" "$TMPAPP/Contents/$LOC/Python"
        fi
    done
    
    sign "$TMPAPP"
    echo "Re-signed successfully."
else
    echo ""
    echo "[2/5] Skipping re-sign (using ad-hoc identity '-')."
    echo "WARNING: Notarization requires a Developer ID certificate."
fi

# Verify signature
echo ""
echo "[3/5] Verifying code signature..."
codesign -vv --deep --strict "$TMPAPP" 2>&1 || true

# Create zip for notarization
echo ""
echo "[4/5] Creating zip for notarization..."
ZIPPATH="/tmp/SAMPSON_notarize_$$.zip"
ditto -c -k --keepParent "$TMPAPP" "$ZIPPATH"

# Submit for notarization
echo ""
echo "[5/5] Submitting to Apple for notarization..."
echo "This may take a few minutes..."
xcrun notarytool submit "$ZIPPATH" \
    --apple-id "$APPLE_ID" \
    --password "$APPLE_APP_PASSWORD" \
    --team-id "$APPLE_TEAM_ID" \
    --wait

rm "$ZIPPATH"

# Staple the ticket
echo ""
echo "Stapling notarization ticket..."
xcrun stapler staple "$TMPAPP"

# Verify Gatekeeper acceptance
echo ""
echo "Verifying Gatekeeper acceptance..."
spctl --assess --type execute --verbose "$TMPAPP" || {
    echo "WARNING: Gatekeeper assessment failed."
    echo "The app may still work but users may see security warnings."
}

# Copy back
echo ""
echo "Copying notarized app back to original location..."
rm -rf "$ABS_APP_PATH"
ditto "$TMPAPP" "$ABS_APP_PATH"
rm -rf "$TMPAPP"

echo ""
echo "=== Notarization Complete ==="
echo "Notarized app: $ABS_APP_PATH"
echo ""
echo "To verify:"
echo "  codesign -vv --deep --strict $ABS_APP_PATH"
echo "  spctl --assess --type execute --verbose $ABS_APP_PATH"
