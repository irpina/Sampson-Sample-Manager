# Bug Tracker

Known issues not yet scheduled for a fix. Add a note when each is resolved.

---

## Open

*No open bugs at this time.*

---

## Resolved

### BUG-001 · Center panel collapses at small window sizes

**Status:** Resolved  
**Reported:** 2026-02-26  
**Severity:** Low — cosmetic, no data loss

**Symptom:**
When the window is resized below approximately 700px wide, the center column
(options panel) shrinks past its content width. Checkboxes, radio buttons,
and the profile combobox truncate or overlap each other.

**Resolution:** Fixed by enforcing minimum window size and adjusting column constraints.

---

### BUG-002 · macOS window oversized and clipped behind menu bar / dock

**Status:** Resolved  
**Reported:** 2026-02-27  
**Severity:** Medium — UI partially hidden on launch; content inaccessible until manually resized

**Symptom:**
On macOS (Retina), the window launches too large and overflows behind the system menu bar at the top and the dock. The bottom panels (status bar, log) and right-side content can be hidden. Additionally, when maximized via the green traffic-light zoom button, the window does not respect the minimum aspect ratio (`MIN_ASPECT_RATIO = 1.38`), potentially collapsing into an unusable tall/narrow shape.

**Resolution:** Fixed DPI scaling calculation for macOS Retina displays.

---

### BUG-003 · Windows console window flashes during file conversion (PyInstaller build)

**Status:** Resolved in v0.6.2  
**Reported:** 2026-03-14  
**Severity:** Medium — UX issue in packaged Windows builds

**Symptom:**
When running the PyInstaller-packaged Windows build (`.exe`), a console window
flashes briefly for every file being converted. This does not occur when
running from source (`python main.py`).

**Root cause:**
`pydub` uses `subprocess.Popen` to call `ffmpeg`/`ffprobe`. On Windows, when
the app is packaged with `--windowed` (no console), each subprocess call
spawns a visible console window that immediately closes.

**Fix:**
Monkey-patch `pydub.utils.Popen` in all modules that use pydub to add the
`CREATE_NO_WINDOW` (0x08000000) flag on Windows.

**Files modified:**
- `conversion.py` — Added patch in `_get_pydub()` and `get_ffmpeg_version()`
- `bpm.py` — Added patch in `_get_pydub()`
- `key.py` — Added patch in `_get_pydub()`
- `preview.py` — Added patch before `mediainfo` call

---

---
*SAMPSON is licensed under the [GNU General Public License v3.0](LICENSE).*
