# Dirtywave File Helper — Sample Utility Expansion Tasks

Expanding from an M8-specific organiser to a universal audio sample manager.
Work incrementally — each task can be committed independently.

---

## Phase 1 — Foundation

These two tasks must land before anything in Phase 2.

---

### Task 1: Hardware profile system

Replace the hard-coded M8 checkbox with a generic, extensible profile selector.

- [ ] `constants.py` — add `PROFILES` ordered dict and `PROFILE_NAMES` list:
  ```python
  PROFILES = {
      "Generic":    {"path_limit": None},   # default — no restrictions
      "M8":         {"path_limit": 127},
      "MPC One":    {"path_limit": 255},
      "SP-404mkII": {"path_limit": 255},
  }
  PROFILE_NAMES = list(PROFILES.keys())
  ```
  > To add a new device in the future: add one entry to this dict. No other file needs changing.

- [ ] `state.py` — remove `m8_var`; add `profile_var = None` (will be `tk.StringVar`, default `"Generic"`)

- [ ] `operations.py` — rename `_m8_truncate(new_name, dest_path_str)` →
  `_apply_path_limit(new_name, dest_path_str, limit)` where `limit` is `int | None`.
  Change the hard-coded `127` to the `limit` parameter.
  Add early return: `if limit is None or len(full) <= limit: return new_name`

- [ ] `preview.py` — update import from `_m8_truncate` to `_apply_path_limit`; update call site to pass `limit` from active profile

- [ ] `builders.py` — in `build_center()`: remove "M8 Friendly" `ttk.Checkbutton`;
  add a `ttk.Label("Hardware profile")` + `ttk.Combobox` bound to `state.profile_var`
  with `values=constants.PROFILE_NAMES, state="readonly"`

- [ ] `builders.py` — in `build_app()`: remove `state.m8_var` trace; add trace on
  `state.profile_var` that calls `preview.refresh_preview()`

- [ ] `builders.py` — in `toggle_theme()`: save/restore `profile_var` alongside the other vars

> **M8 behaviour preserved:** Selecting "M8" in the dropdown applies `path_limit=127`,
> identical to the old checkbox. "Generic" (default) applies no truncation.

---

### Task 2: Shared rename/path helper

Extract the rename logic that currently lives in duplicate inside both `_run_worker()` and
`_populate_preview()` into one authoritative function. Eliminates the risk of the preview
showing different results than the actual run.

- [ ] `operations.py` — add `_compute_output()` immediately below `_apply_path_limit()`:

  ```python
  def _compute_output(f, source_root, dest, no_rename, struct_mode, path_limit):
      """
      Return (new_filename, rel_subfolder) for a single source file.

      rel_subfolder is the subfolder relative to dest where the file lands:
        ""         — flat mode (file goes directly in dest)
        "Kicks"    — parent mode (file goes in dest/Kicks/)
        "Kicks/808" — mirror mode (file goes in dest/Kicks/808/)
      """
      # Filename
      new_name = f.name if no_rename else f"{f.parent.name}_{f.name}"

      # Subfolder
      if struct_mode == "flat":
          rel_sub = ""
      elif struct_mode == "mirror":
          try:
              rel_sub = str(f.parent.relative_to(source_root))
          except ValueError:
              rel_sub = ""
          if rel_sub == ".":
              rel_sub = ""
      elif struct_mode == "parent":
          rel_sub = f.parent.name if f.parent != source_root else ""
      else:
          rel_sub = ""

      # Path limit
      effective_dest = str(Path(dest) / rel_sub) if rel_sub else str(dest)
      if path_limit is not None:
          new_name = _apply_path_limit(new_name, effective_dest, path_limit)

      return new_name, rel_sub
  ```

- [ ] `preview.py` — import `_compute_output`; replace the inline rename logic in
  `_populate_preview()` with a call to `_compute_output(f, source_root, dest, ...)`;
  use the returned `rel_sub` to populate the new "Subfolder" tree column (see Task 3)

> `_run_worker()` will be updated in Task 4 to call this same function.

---

## Phase 2 — Core Features

Depend on both Phase 1 tasks being complete.

---

### Task 3: Folder structure UI controls + preview tree column

Let the user choose how files are arranged in the destination.

- [ ] `state.py` — add `struct_mode_var = None` (will be `tk.StringVar`, default `"flat"`)

- [ ] `builders.py` — in `build_center()`, add below the profile combobox:
  ```
  Label: "Folder structure"
  Radio: "Flat — all files together"      → struct_mode_var = "flat"
  Radio: "Mirror source tree"             → struct_mode_var = "mirror"
  Radio: "One folder per parent"          → struct_mode_var = "parent"
  ```
  > "One folder per parent" handles Splice downloads naturally — each pack becomes a subfolder.

- [ ] `builders.py` — in `build_app()`: add trace on `state.struct_mode_var` → `preview.refresh_preview()`

- [ ] `builders.py` — in `toggle_theme()`: save/restore `struct_mode_var`

- [ ] `builders.py` — in `build_deck_b()`: add a third `"Subfolder"` column to `state.preview_tree`
  (header text `"Subfolder"`, initial `width=0` so it is hidden in flat mode)

- [ ] `preview.py` — in `refresh_preview()`: after calling `_compute_output()`, set the
  "Subfolder" column width to `_px(140)` when struct_mode is not `"flat"`, or `0` when flat;
  populate column with `rel_sub` value per row

---

### Task 4: Wire `_run_worker()` to use `_compute_output()`

Make the actual file operations match the preview.

- [ ] `operations.py` — `run_tool()`: read `state.struct_mode_var` and resolve
  `path_limit = constants.PROFILES[state.profile_var.get()]["path_limit"]`;
  pass both to the worker thread

- [ ] `operations.py` — `_run_worker()` signature: add `struct_mode` and `path_limit` params

- [ ] `operations.py` — inside the file loop, replace the current inline rename logic with:
  ```python
  new_name, rel_sub = _compute_output(f, source, dest,
                                      no_rename, struct_mode, path_limit)
  sub_dir = dest / rel_sub if rel_sub else dest
  target  = sub_dir / new_name
  sub_dir.mkdir(parents=True, exist_ok=True)
  ```

- [ ] `operations.py` — update log message to include subfolder when non-empty:
  ```python
  dest_display = f"{rel_sub}/{new_name}" if rel_sub else new_name
  ```

---

## Phase 3 — Polish

---

### Task 5: Version bump

- [ ] `builders.py` — `build_status_bar()`: update version label `"v0.10"` → `"v0.11"`
- [ ] *(Optional)* Update subtitle in `build_header()` from `"Audio Sample Organiser"`
  to `"Universal Audio Sample Manager"`

---

## Later (separate tasks)

---

### Task 6: Audio sample preview

Play a selected file directly from the browser without leaving the app.

- Trigger: click or keyboard shortcut on a file in Deck A browser
- Library options: `sounddevice` + `soundfile` (no GUI dependency),
  or `pygame.mixer` (heavier but wider format support)
- UI: small ▶ / ■ button in the browser row, or space-bar shortcut
- Must not block the UI — playback in a daemon thread

> Kept separate from this expansion intentionally. Requires evaluating external
> dependencies and packaging implications for PyInstaller.

---

### Task 7: App rename

Rename from "Dirtywave File Helper" to a device-neutral name when branding is decided.

- `main.py` — `state.root.title()`
- `builders.py` — `build_header()` title label
- `DirtywaveFileHelper.spec` — `name` field + output exe name
- `README.md` — all references

> Deferred until the new name is chosen. No functional changes.
