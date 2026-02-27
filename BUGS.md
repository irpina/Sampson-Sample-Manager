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

## Resolved

*(none yet)*
