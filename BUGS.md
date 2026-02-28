# Bug Tracker

Known issues not yet scheduled for a fix. Add a note when each is resolved.

---

## Open

---

### BUG-001 · Center panel collapses at small window sizes

**Status:** Open
**Reported:** 2026-02-26
**Severity:** Low — cosmetic, no data loss

**Symptom:**
When the window is resized below approximately 700px wide, the center column
(options panel) shrinks past its content width. Checkboxes, radio buttons,
and the profile combobox truncate or overlap each other.

**Root cause:**
`root_frame.columnconfigure(1, weight=2, minsize=_px(180))` in `builders.py`.
The 180px logical minimum is too narrow for the current center panel content
(which now includes folder-structure radios and a hardware profile combobox).
No minimum window size is set on the root window.

**Files affected:**
- [builders.py](builders.py) — `build_app()`, `root_frame.columnconfigure(1, ...)`
- [main.py](main.py) — no `state.root.minsize(...)` call present

**Potential fix (pick one):**
Option A — enforce a minimum window size in `main.py`:
```python
state.root.minsize(_px(780), _px(520))
```
Option B — increase center column minsize in `builders.py`:
```python
root_frame.columnconfigure(1, weight=2, minsize=_px(230))
```
Option A preferred — it also prevents the decks from collapsing.

---

---

### BUG-002 · macOS window oversized and clipped behind menu bar / dock

**Status:** Open
**Reported:** 2026-02-27
**Severity:** Medium — UI partially hidden on launch; content inaccessible until manually resized

**Symptom:**
On macOS (Retina), the window launches too large and overflows behind the system menu bar at the top and the dock. The bottom panels (status bar, log) and right-side content can be hidden. Additionally, when maximized via the green traffic-light zoom button, the window does not respect the minimum aspect ratio (`MIN_ASPECT_RATIO = 1.38`), potentially collapsing into an unusable tall/narrow shape.

**Root cause:**
`_compute_dpi_scale()` in `dpi.py` returns `NSScreen.mainScreen().backingScaleFactor()` — which is `2.0` on Retina displays. This value is then used by `_px()` to double all window/widget pixel values. However, **tkinter on macOS already works in logical points** (1 pt = 2 physical pixels on Retina); CTK also handles Retina scaling internally. The `backingScaleFactor` multiplier is therefore applied twice, making the initial window `2200×1560` logical points — larger than most Mac screens (typically 1280–1800 pts wide).

**Files affected:**
- [dpi.py](dpi.py) — `_compute_dpi_scale()` macOS branch returns wrong value
- [main.py](main.py) — startup geometry and minsize use `_px()` which is 2× on macOS; no screen-clamp; no aspect-ratio binding

**Fix:** See [PLAN_MACOS_SCALING.md](PLAN_MACOS_SCALING.md) for the full implementation plan.

---

## Resolved

*(none yet)*
