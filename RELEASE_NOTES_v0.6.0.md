## What's New in SAMPSON v0.6.0

### 🔍 Smart Search & Filter (Deck B)
Search your sample library with structured queries:
- **Text search:** `kick` — filename substring match
- **BPM filters:** `BPM:120` (exact), `BPM:100-140` (range), `BPM:12*` (wildcard)
- **Note filters:** `Note:C` or `Note:F#` — root note match
- **Duration filters:** `MinLength:10` or `MaxLength:90` — seconds
- **Combined:** `kick BPM:120-140 Note:C MinLength:5` — AND logic

### 🎵 Musical Key Detection
- Automatic root pitch class detection for all audio files
- Results cached to `~/.sampson/key_cache.json` for instant reload
- Double-click any Key cell to manually override
- "Fresh scan" option to re-detect and update cached values

### 📊 Column Sorting (Deck B)
- Click **BPM**, **Note**, or **Length** headers to sort
- Toggle: Ascending ▲ → Descending ▼ → No sort
- Sorting applies before filtering for precise control

### ⏱️ Duration Column
- New **Length** column showing audio file duration
- Fast header reading for WAV/AIFF files
- MP3/FLAC/OGG via ffprobe fallback

### ✨ Other Improvements
- BPM/Key columns now visible when cached data exists (even if detection toggle is off)
- Fixed center panel scrolling issues when hovering over deck areas
- Improved key detection accuracy for short oneshot samples
- Visual polish: fixed unrounded corners on center panel

---

**Full Changelog:** v0.5.8...v0.6.0
