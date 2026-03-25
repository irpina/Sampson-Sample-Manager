# SAMPSON v0.6.1

## Fixes

### macOS Launch Issues
- **Fixed race condition causing app to fail launching on double-click**  
  Added single instance lock to prevent multiple simultaneous launches
  
- **Fixed AppKit activation timing**  
  Proper app activation ensures window appears correctly on launch

### FFmpeg Detection
- **Fixed ffmpeg not being detected in bundled app**  
  Added proper bundle path resolution for static_ffmpeg binaries

## Changes
- Add file locking mechanism (`~/.sampson/app.lock`)
- Add macOS app activation handling
- Update Info.plist with better launch behavior settings
- Version bump to 0.6.1

## Download

**macOS (Apple Silicon & Intel)**  
`SAMPSON_mac_v0.6.1.zip` - Signed and notarized

Requires macOS 12.0 or later.
