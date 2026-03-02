# Plan: Collapsible Centre Panel Sections (v0.5.1)

## Context

The centre panel now has four option sections (Output structure, Target device, Audio
conversion, BPM analysis) that together overflow the column height at typical window sizes.
Rather than a scrollbar, collapsible accordion-style section headers give the user control
over what is visible while keeping the Run button and transport always reachable.

---

## Approach

Replace each section's `separator + static label` pair with a single **clickable header
button** (`▼ Section name` / `▶ Section name`).  Clicking the header calls
`widget.grid_remove()` on every content widget in that section (hiding them without
destroying them) or `widget.grid()` to restore.  The button text updates to reflect state.

No new classes are introduced — a single `_section_header()` helper function in
`builders.py` handles all four sections.

**Always visible (never collapse):**
- Move / Dry run / Keep names checkboxes (rows 0–1)
- Transport controls, Run, Clear log (rows 13–16)

**Collapsible (default open):**
- Output structure
- Target device
- Audio conversion
- BPM analysis

---

## New Row Layout in `build_center()`

```
Row 0   Move files  |  Dry run           [always visible]
Row 1   Keep original names              [always visible]
Row 2   ▼/▶  Output structure           [header button]
Row 3   struct_frame (Flat|Mirror|…)    [content — grid_remove on collapse]
Row 4   ▼/▶  Target device              [header button]
Row 5   profile CTkOptionMenu           [content]
Row 6   ▼/▶  Audio conversion           [header button]
Row 7   conv_cb  (Convert files cb)     [content]
Row 8   conv_opts (format/sr/bd/ch)     [content]
Row 9   ▼/▶  BPM analysis              [header button]
Row 10  bpm_cb  (Detect BPM cb)        [content]
Row 11  bpm_opts (Append BPM cb)        [content]
Row 12  expanding spacer                [weight=1]
Row 13  transport controls
Row 14  separator
Row 15  Run button
Row 16  Clear log
```

(Saves 4 rows vs current layout; standalone separator lines are replaced by the headers.)

---

## Helper: `_section_header()`

Add to `builders.py`, just before `build_center()`:

```python
def _section_header(frame, row, label, content_widgets, default_open=True,
                    key=None):
    """
    Place a collapsible section header at `row` in `frame`.

    content_widgets — list of widgets already placed in `frame`'s grid;
                      their grid info is snapshotted so grid() restores them
                      to the original position.
    key             — optional string key used to look up saved open/close
                      state from state._section_open (theme-toggle persistence).
    Returns the toggle function.
    """
    # Snapshot grid info before any possible grid_remove call
    _grid_info = {w: w.grid_info() for w in content_widgets}

    # Honour saved state from theme toggle
    if key and key in state._section_open:
        default_open = state._section_open[key]

    _open = [default_open]   # mutable cell avoids nonlocal on Python ≤ 3.9

    def _toggle(*_):
        _open[0] = not _open[0]
        btn.configure(text=f"{'▼' if _open[0] else '▶'}  {label}")
        if key:
            state._section_open[key] = _open[0]
        for w in content_widgets:
            if _open[0]:
                w.grid(**_grid_info[w])
            else:
                w.grid_remove()

    btn = ctk.CTkButton(
        frame,
        text=f"{'▼' if default_open else '▶'}  {label}",
        fg_color=theme.BG_SURF1,
        text_color=theme.FG_MUTED,
        hover_color=theme.BG_SURF2,
        anchor="w",
        corner_radius=4,
        height=_px(24),
        font=(theme.FONT_UI, 9),
        command=_toggle,
        border_width=0,
    )
    btn.grid(row=row, column=0, columnspan=2, sticky="ew", padx=12, pady=(6, 2))

    if not default_open:
        for w in content_widgets:
            w.grid_remove()

    return _toggle
```

### Important: snapshot timing

`_grid_info` must be captured **after** each content widget has been placed with
`.grid(...)` but **before** `_section_header()` is called.  The implementation order
in `build_center()` therefore is:

1. Create & grid the content widgets for a section.
2. Immediately call `_section_header(frame, row, label, [w1, w2, …], key=…)` — this
   places the header button at `row` and snapshots the grid positions.

Because the header button is placed at a lower row number than the content (e.g. header
at row 2, content at row 3), grid does not care about insertion order.

---

## State: `state._section_open`

Add to `state.py`:

```python
_section_open = {}   # {"struct": True, "device": True, "conversion": True, "bpm": True}
```

---

## Changes to `toggle_theme()` in `builders.py`

Save and restore section open/close state across theme rebuilds.  Because
`_section_header()` reads from `state._section_open` automatically when `key` is
provided, only `state._section_open` needs to survive the rebuild — no new
`saved_*` vars required.  `state._section_open` is a plain dict on the module, so it
persists through `toggle_theme()` naturally (only widget objects are destroyed).

No extra save/restore lines needed.

---

## Changes to `build_center()` row numbering

### Remove
- The four `ctk.CTkFrame(…, height=1, …)` separator lines (rows 2, 5, 8, 12 in the
  current layout).
- The four `ctk.CTkLabel(…, text="…section name…")` static labels.

### Add
Four `_section_header()` calls (one per section) at rows 2, 4, 6, 9.

### Update `frame.rowconfigure` block

```python
frame.rowconfigure(5,  weight=0, minsize=_px(40))   # profile dropdown
frame.rowconfigure(8,  weight=0, minsize=_px(140))  # conv_opts
frame.rowconfigure(11, weight=0, minsize=_px(60))   # bpm_opts
frame.rowconfigure(12, weight=1)                    # expanding spacer
frame.rowconfigure(13, weight=0, minsize=_px(50))   # transport
frame.rowconfigure(15, weight=0, minsize=_px(45))   # Run
frame.rowconfigure(16, weight=0, minsize=_px(50))   # Clear log
```

---

## Version bump

`build_status_bar()`: `"v0.5.0"` → `"v0.5.1"`

---

## Files changed

| File | Change |
|------|--------|
| `builders.py` | Add `_section_header()` helper; rewrite `build_center()` row layout; version bump |
| `state.py` | Add `_section_open = {}` |

No changes to `operations.py`, `preview.py`, `theme.py`, `bpm.py`, or any other file.

---

## Verification

1. `python main.py` — centre panel shows all four section headers with `▼`.
2. Click each header — content collapses; header changes to `▶`.  Panel height shrinks.
3. Click again — expands back.  All controls functional.
4. Toggle theme — collapsed/open state preserved.
5. Run with conversion + BPM enabled while sections are collapsed — operations complete
   normally (collapse is display-only; state vars are unchanged).
6. Window resize — collapsing sections frees enough vertical space that all controls
   remain reachable at min window height.
