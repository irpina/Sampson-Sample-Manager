# Agent Plan: Fix macOS Window Scaling (BUG-002)

## Goal

Fix two related macOS window problems:
1. App launches with a window too large for the screen — content hidden behind menu bar and dock
2. No aspect-ratio enforcement when the user zooms/resizes the window

---

## Root Cause

`_compute_dpi_scale()` in `dpi.py` returns `NSScreen.mainScreen().backingScaleFactor()` on macOS, which is `2.0` on Retina displays. `_px()` then doubles every window and widget dimension. But **tkinter on macOS operates in logical points** — 1 pt = 2 physical pixels on Retina — and CTK handles Retina rendering internally. The backing scale factor is therefore applied a second time on top of the OS mapping, making the startup window `2200×1560` logical points. Most Mac screens are 1280–1800 pts wide, so the window spills behind the menu bar and dock.

---

## Changes Required

### 1 · `dpi.py` — Fix `_compute_dpi_scale()` for macOS

Remove the `backingScaleFactor` branch and return `1.0` on macOS:

**Current code (lines 35–43):**
```python
if sys.platform == "darwin":
    try:
        from AppKit import NSScreen  # provided by pyobjc-framework-Cocoa
        scale = NSScreen.mainScreen().backingScaleFactor()
        if scale and scale > 0:
            return float(scale)
    except Exception:
        pass
    return 1.0
```

**Replace with:**
```python
if sys.platform == "darwin":
    return 1.0  # tkinter uses logical points; CTK handles Retina internally
```

> **Why:** `backingScaleFactor` maps physical pixels → logical points at the OS level. tkinter already receives coordinates in logical points. Using it for `_px()` doubles all sizes.

---

### 2 · `main.py` — Clamp startup geometry to the usable screen area

After `state.root = ctk.CTk()` is created (but before `.geometry()` is called), compute the usable screen dimensions and cap the initial window size.

Replace the current geometry block:
```python
from dpi import _px
state.root.geometry(f"{_px(1100)}x{_px(780)}")
state.root.minsize(_px(MIN_WINDOW_WIDTH), _px(MIN_WINDOW_HEIGHT))
```

**Replace with:**
```python
from dpi import _px, _usable_screen_size
win_w, win_h = _usable_screen_size(state.root, _px(1100), _px(780))
state.root.geometry(f"{win_w}x{win_h}")
state.root.minsize(_px(MIN_WINDOW_WIDTH), _px(MIN_WINDOW_HEIGHT))
```

Add `_usable_screen_size()` to `dpi.py` (see section 3 below).

---

### 3 · `dpi.py` — Add `_usable_screen_size()` helper

Add this function at the bottom of `dpi.py` (after `_px`):

```python
def _usable_screen_size(root, desired_w: int, desired_h: int) -> tuple[int, int]:
    """
    Return (width, height) clamped to the usable screen area.

    On macOS, uses AppKit visibleFrame to exclude menu bar and dock.
    On other platforms, uses tkinter screen dimensions with no adjustment.
    """
    if sys.platform == "darwin":
        try:
            from AppKit import NSScreen
            frame = NSScreen.mainScreen().visibleFrame()
            max_w = int(frame.size.width) - 40   # small side margin
            max_h = int(frame.size.height) - 20  # small bottom margin
            return min(desired_w, max_w), min(desired_h, max_h)
        except Exception:
            pass
        # Fallback: tkinter screen size minus rough menu bar/dock estimate
        root.update_idletasks()
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        return min(desired_w, sw - 40), min(desired_h, sh - 95)

    return desired_w, desired_h
```

> `visibleFrame()` returns the screen area excluding the menu bar and dock — exactly what we want. The fallback subtracts 95pt (≈ 25pt menu bar + 70pt dock) as a safe estimate.

---

### 4 · `main.py` — Enforce aspect ratio on resize/zoom

Add a `<Configure>` binding after `build_app()` to prevent the window from collapsing into an unusable tall/narrow shape when the user resizes or uses macOS Zoom:

```python
import sys as _sys
if _sys.platform == "darwin":
    from dpi import MIN_ASPECT_RATIO
    def _enforce_aspect(event):
        if event.widget is not state.root:
            return
        w, h = event.width, event.height
        if w <= 1 or h <= 1:
            return
        if (w / h) < MIN_ASPECT_RATIO:
            new_h = int(w / MIN_ASPECT_RATIO)
            state.root.geometry(f"{w}x{new_h}")
    state.root.bind("<Configure>", _enforce_aspect)
```

Place this block immediately after `build_app()` and before `state.root.mainloop()`.

> `MIN_ASPECT_RATIO = 1.38` is already defined in `dpi.py`. The binding only fires on macOS and only adjusts the height when the window becomes too narrow relative to its width.

---

### 5 · Version bump

In `builders.py`, find `build_status_bar()` and update:
```python
# Change:
ctk.CTkLabel(frame, text="v0.3.2", ...)
# To:
ctk.CTkLabel(frame, text="v0.3.3", ...)
```

---

## Files to Edit

| File | Change |
|------|--------|
| `dpi.py` | Replace macOS branch in `_compute_dpi_scale()` with `return 1.0`; add `_usable_screen_size()` |
| `main.py` | Use `_usable_screen_size()` for geometry; add macOS `<Configure>` aspect-ratio binding |
| `builders.py` | Version bump to `v0.3.3` |

No other files need changing.

---

## Verification

After implementing:

```bash
python main.py
```

- [ ] Window opens fully visible — no content behind menu bar or dock
- [ ] Window fits within the screen without scrolling
- [ ] Dragging the window edge to an extreme narrow width auto-corrects the height
- [ ] Dark/Light theme toggle still works (paths and settings preserved)
- [ ] Audio playback still works

DPI sanity check (confirm scale is now 1.0 on macOS):
```bash
python -c "
import sys; sys.path.insert(0, '.')
import state, dpi
state._dpi_scale = dpi._compute_dpi_scale()
print('DPI scale:', state._dpi_scale)  # must be 1.0 on macOS
"
```

---

## Architecture Reminders

- Import order matters — no circular imports. `dpi.py` imports only `state`. `main.py` imports `dpi`, `state`, `theme`, `builders`.
- `import state` then `state.<attr>` — never `from state import x`
- Do not call `tk.call('tk', 'scaling', ...)` — CTK manages its own DPI
- All UI updates from threads: `state.root.after(0, callback)`
- Always update the version label in `build_status_bar()` in `builders.py`
