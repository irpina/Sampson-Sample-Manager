# Audio Sample Preview — Task File

Adds the ability to click a sample in Deck B and hear it, with
Back / Play-Stop / Forward transport controls in the center panel.

Cross-reference: see `TASKS.md` → "Later → Task 6" for the original stub.

---

## Architecture Overview

```
New module: playback.py
  → imports: state, theme, constants
  → sits between preview.py and builders.py in the import chain

Module dependency addition:
  builders.py → playback (for button commands)
  preview.py  → (no change; playback is wired in builders)
```

**Audio library:** `pygame.mixer`
- Supports all formats in AUDIO_EXTS: WAV, AIFF, FLAC, MP3, OGG
- Single pip install; reliable with PyInstaller on Windows
- Adds ~10MB to the packaged exe
- Install: `pip install pygame`
- PyInstaller hook: add `--hidden-import pygame` to spec if needed

**Source path in tree:** The preview tree needs to expose the actual
source file path so playback can open it. Currently the tree stores
(original, renamed, subfolder). A hidden 4th column stores the real path.

**Transport buttons:** Three icon buttons below the profile combobox,
above the Run separator. They sit inside a small `tk.Frame` so they can
be grouped horizontally while the rest of the center panel stays vertical.

---

## Phase 1 — Foundation

---

### Task P1: Dependencies + state variables

- [ ] Install pygame: `pip install pygame`

- [ ] `state.py` — add playback state vars:
  ```python
  _playback_file    = None   # Path of file currently loaded (or None)
  _is_playing       = False  # True while pygame.mixer is playing
  transport_prev_btn = None  # ttk.Button refs for enabling/disabling
  transport_play_btn = None
  transport_next_btn = None
  ```

- [ ] Verify `pygame.mixer.init()` works on the dev machine with a .wav file
  before committing this task

> **PyInstaller note:** When packaging, pygame brings its own DLLs.
> The `.spec` file may need `--collect-data pygame` or
> `--hidden-import pygame._view`. Test the exe after Task P6.

---

### Task P2: Hidden source-path column in preview tree

The playback code needs the actual file path; the preview tree is the
shared data source between preview and playback.

- [ ] `builders.py` — `build_deck_b()`: add 4th hidden column to treeview:
  ```python
  columns=("original", "renamed", "subfolder", "srcpath")
  ...
  state.preview_tree.column("srcpath", width=0, minwidth=0, stretch=False)
  state.preview_tree.heading("srcpath", text="")
  ```

- [ ] `preview.py` — `_populate_preview()`: pass real path as 4th value:
  ```python
  state.preview_tree.insert("", "end",
      values=(f.name, new_name, rel_sub, str(f)),
      tags=(tag,))
  ```

> `str(f)` is the absolute path on disk. No rename or path-limit logic
> applies to the source path — it's read-only metadata for playback.

---

## Phase 2 — Core Playback

---

### Task P3: Create `playback.py`

New module. Place it in the import chain: `preview.py → playback.py → builders.py`.

```
constants.py → state.py → dpi.py → theme.py → log_panel.py →
operations.py → browser.py → preview.py → playback.py → builders.py → main.py
```

- [ ] Create `playback.py` with:

  ```python
  import pygame.mixer as _mixer
  from pathlib import Path

  import state
  import theme

  _mixer.init()
  _current_index = -1   # index into preview tree item list


  def _tree_items():
      """Return list of all item IDs in preview tree."""
      return list(state.preview_tree.get_children())


  def _load_index(idx):
      """Select and prepare the file at tree index idx without playing."""
      global _current_index
      items = _tree_items()
      if not items or not (0 <= idx < len(items)):
          return
      _current_index = idx
      iid = items[idx]
      state.preview_tree.selection_set(iid)
      state.preview_tree.see(iid)
      src = state.preview_tree.set(iid, "srcpath")
      state._playback_file = Path(src) if src else None
      _update_transport_state()


  def play():
      """Play or stop the currently selected file."""
      if _mixer.music.get_busy():
          stop()
          return
      if not state._playback_file or not state._playback_file.is_file():
          return
      try:
          _mixer.music.load(str(state._playback_file))
          _mixer.music.play()
          state._is_playing = True
          _update_transport_state()
          # Poll for completion using root.after
          state.root.after(200, _poll_playback)
      except Exception:
          state._is_playing = False


  def stop():
      _mixer.music.stop()
      state._is_playing = False
      _update_transport_state()


  def next_file():
      stop()
      items = _tree_items()
      if not items:
          return
      idx = min(_current_index + 1, len(items) - 1)
      _load_index(idx)


  def prev_file():
      stop()
      idx = max(_current_index - 1, 0)
      _load_index(idx)


  def on_tree_select(event):
      """Called on ButtonRelease-1 on the preview tree."""
      iid = state.preview_tree.identify_row(event.y)
      if not iid:
          return
      items = _tree_items()
      if iid in items:
          stop()
          _load_index(items.index(iid))


  def _poll_playback():
      """Re-check every 200ms; update button when track ends naturally."""
      if _mixer.music.get_busy():
          state.root.after(200, _poll_playback)
      else:
          state._is_playing = False
          _update_transport_state()


  def _update_transport_state():
      """Sync play/stop button label and enable/disable transport buttons."""
      if state.transport_play_btn:
          icon = "■" if state._is_playing else "▶"
          state.transport_play_btn.configure(text=icon)
      has_file = state._playback_file is not None
      items    = _tree_items()
      can_prev = has_file and _current_index > 0
      can_next = has_file and _current_index < len(items) - 1
      for btn, enabled in [
          (state.transport_prev_btn, can_prev),
          (state.transport_next_btn, can_next),
      ]:
          if btn:
              btn.state(["!disabled"] if enabled else ["disabled"])
  ```

---

### Task P4: Transport UI in `build_center()`

Add a horizontal row of three icon buttons between the profile combobox and the
Run separator. The spacer row stays above them, so transport floats just above Run.

- [ ] `builders.py` — add `import playback` at top (after `import preview`)

- [ ] `builders.py` — in `build_center()`, replace the spacer + existing separator block:

  Current:
  ```
  Row 11: spacer (rowconfigure weight=1)
  Row 12: Separator
  Row 13: Run
  Row 14: Clear log
  ```

  New:
  ```
  Row 11: spacer (rowconfigure weight=1)   ← unchanged
  Row 12: Transport button row             ← NEW
  Row 13: Separator                        ← was 12
  Row 14: Run                              ← was 13
  Row 15: Clear log                        ← was 14
  ```

  Transport row implementation:
  ```python
  transport_frame = tk.Frame(frame, bg=theme.BG_SURFACE)
  transport_frame.grid(row=12, column=0, pady=(0, 6))

  state.transport_prev_btn = ttk.Button(
      transport_frame, text="◀", style="Icon.TButton",
      command=playback.prev_file, width=3)
  state.transport_prev_btn.pack(side="left", padx=4)
  state.transport_prev_btn.state(["disabled"])

  state.transport_play_btn = ttk.Button(
      transport_frame, text="▶", style="Icon.TButton",
      command=playback.play, width=3)
  state.transport_play_btn.pack(side="left", padx=4)

  state.transport_next_btn = ttk.Button(
      transport_frame, text="▶▶", style="Icon.TButton",
      command=playback.next_file, width=3)
  state.transport_next_btn.pack(side="left", padx=4)
  state.transport_next_btn.state(["disabled"])
  ```

  > `Icon.TButton` already exists in `theme.py` — no new styles needed.
  > `width=3` keeps the buttons compact; adjust to taste.

- [ ] Shift separator, Run, Clear log from rows 12/13/14 → 13/14/15

---

## Phase 3 — Wire-up & Polish

---

### Task P5: Wire click binding + stop on navigate

- [ ] `builders.py` — `build_deck_b()`: bind tree click to playback handler:
  ```python
  state.preview_tree.bind("<ButtonRelease-1>", playback.on_tree_select)
  ```
  (Add after the existing `<Motion>` and `<Leave>` bindings)

- [ ] `preview.py` — `refresh_preview()`: call `playback.stop()` when source
  directory changes (prevents playing a file that no longer exists in the tree):
  ```python
  # At top of refresh_preview(), before deleting tree contents:
  import playback          # deferred to avoid circular import at module level
  playback.stop()
  ```
  Actually — to avoid a circular import, add a `reset()` function to `playback.py`
  that just calls `stop()` and resets `_current_index = -1`. Call it from
  `preview.refresh_preview()` via `state.root.after(0, ...)` if needed,
  or wire a trace in `build_app()` instead:
  ```python
  state.active_dir_var.trace_add("write",
      lambda *_: playback.stop() or setattr(playback, "_current_index", -1))
  ```

- [ ] `toggle_theme()` in `builders.py`: call `playback.stop()` before tearing
  down widgets (prevents audio playing while UI is rebuilt)

---

### Task P6: Version bump + PyInstaller validation

- [ ] `builders.py` — `build_status_bar()`: bump version `"v0.11"` → `"v0.12"`

- [ ] Test the packaged exe:
  - `pyinstaller --onefile --windowed --name "SAMPSON" main.py`
  - Verify pygame audio plays in the exe, not just in the dev interpreter
  - If DLLs are missing, add `--collect-data pygame` to the pyinstaller command
    and update the `.spec` file accordingly

---

## File Change Summary

| File | Changes |
|---|---|
| `state.py` | Add `_playback_file`, `_is_playing`, transport button refs |
| `playback.py` | **New module** — all playback logic |
| `builders.py` | Add transport row to `build_center()`; tree click binding; stop on theme toggle; import playback; version bump |
| `preview.py` | Add 4th `"srcpath"` column value in `_populate_preview()` |
| *(no other files)* | `operations.py`, `browser.py`, `theme.py`, `constants.py` untouched |
