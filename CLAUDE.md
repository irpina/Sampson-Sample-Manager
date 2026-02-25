# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running and building

```bash
# Run the app
python main.py

# Package as a standalone Windows exe (requires pyinstaller)
pyinstaller --onefile --windowed --name "DirtywaveFileHelper" main.py
# Output: dist/DirtywaveFileHelper.exe
```

No test suite exists. There are no linting or formatting configurations.

## Workflow rules

- **Always increment the version number** after every change — edit the `text="vN"` label in `build_status_bar()` inside `builders.py`.
- **Always commit** after completing a change.

## Architecture

The app is a single-window tkinter GUI. All state is held in `state.py` as plain module attributes. Every other module does `import state` and reads/writes via `state.xxx` — **never** `from state import x`, because that creates a local copy that won't reflect reassignments.

**Module dependency order (no circular imports):**

```
constants.py  ← no deps
state.py      ← no deps
dpi.py        ← state
theme.py      ← state, dpi
log_panel.py  ← state, theme
operations.py ← state, theme, constants, log_panel
browser.py    ← state, theme, constants
preview.py    ← state, theme, constants, dpi, operations
builders.py   ← state, theme, dpi, browser, preview, log_panel, operations
main.py       ← state, theme, dpi, builders
```

**Key design points:**

- **Colors** live as module-level variables in `theme.py` (e.g. `theme.CYAN`). `_apply_theme_colors()` reassigns them in-place using `global`; calling code re-reads `theme.CYAN` after each rebuild so the new values take effect.
- **Theme toggle** (`builders.toggle_theme`) destroys all widgets, calls `_apply_theme_colors` + `setup_styles` + `build_app`, then restores saved paths. It is in `builders.py` (not `theme.py`) to avoid a circular import.
- **DPI scaling** — `state._dpi_scale` is set once at startup in `main.py`. All pixel values go through `dpi._px(n)` which multiplies by that scale. Call `from dpi import _px` in any module that sizes widgets.
- **Background threads** — scanning and file operations run on daemon threads. All UI updates must use `state.root.after(0, ...)`.
- **Preview debounce** — `preview.on_active_dir_changed` cancels any pending `state._preview_after` callback and reschedules a 300 ms refresh to avoid flooding the thread pool during rapid navigation.
- **Rename scheme** — `{parent_folder_name}_{filename}`. Skipped when `state.no_rename_var` is set. M8 Friendly mode additionally truncates the stem so the full destination path stays ≤ 127 chars (`operations._m8_truncate`).
