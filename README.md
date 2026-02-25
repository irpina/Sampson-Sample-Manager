# Dirtywave File Helper

A desktop GUI tool for organising audio samples for the **Dirtywave M8** tracker (and similar devices). It lets you browse a source library, preview how files will be renamed, then copy or move them into a flat destination folder — all without leaving the app.

---

## Features

- **Two-deck layout** — Deck A (source) and Deck B (destination) mirror the M8's workflow
- **Inline file browser** — navigate your source library by clicking folders; audio files are listed with a ♪ icon
- **Live rename preview** — instantly shows how each file will be renamed before you commit
- **Copy or Move** — choose to copy files (default, non-destructive) or move them
- **Dry run mode** — default-on; logs every action without touching the filesystem
- **M8 Friendly mode** — enforces Dirtywave M8's 127-character SD-card path limit by truncating stems (extension always preserved)
- **Dark / Light theme** — toggle between a dark MD3 palette and a warm 60s/70s pastel theme
- **Operation log** — colour-coded log panel (red = move, green = copy, yellow = dry run, cyan = done)
- **Progress bar** — tracks processing in real time via a background thread

### Supported formats

`.wav` · `.aiff` · `.aif` · `.flac` · `.mp3` · `.ogg`

---

## How it works

When you run the tool, each audio file is renamed using the pattern:

```
{parent_folder_name}_{original_filename}
```

For example, a file at `Drums/Kicks/kick_01.wav` becomes `Kicks_kick_01.wav` in the destination folder. This keeps a single flat folder usable on the M8 while preserving the context of where each sample came from.

---

## Requirements

- Python 3.8 or later
- No third-party packages — uses only the standard library (`tkinter`, `shutil`, `threading`, `pathlib`)

---

## Running the app

```bash
python main.py
```

On Windows you can also double-click `main.py` if `.py` is associated with Python.

---

## Usage

1. **Set the source (Deck A)**
   - Click **Browse** or type a path into the source field.
   - The file browser populates with subfolders and audio files.
   - Click a folder to navigate into it; click **↑** or the `..` entry to go up.

2. **Set the destination (Deck B)**
   - Click **Browse** or type a path into the destination field.
   - The destination should be a folder on your M8's SD card (or any target folder).

3. **Check the preview**
   - Deck B's table shows every audio file found in the current source directory tree alongside its renamed form.
   - Hover over a name in the **Will become** column for a full-path tooltip.

4. **Configure options (centre panel)**
   | Option | Default | Description |
   |--------|---------|-------------|
   | Move files | Off | Move instead of copy. Off = copy (safe). |
   | Dry run | **On** | Log actions without writing any files. Turn off to commit changes. |
   | M8 Friendly | Off | Truncate filenames so the full destination path is ≤ 127 characters. |

5. **Click Run** (or press **Enter**)
   - The status bar and log panel update in real time.
   - The Run button re-enables when processing is complete.
   - Use **Clear log** to reset the log panel between runs.

---

## M8 path limit

The Dirtywave M8 enforces a **127-character** maximum for file paths on its SD card. When **M8 Friendly** is enabled the tool calculates:

```
available_stem_chars = 127 − len(destination_path) − 1 − len(extension)
```

and silently truncates the filename stem to fit, always keeping the file extension intact.

---

## Theming

Click the **☀ Light** / **☾ Dark** label in the top-right corner to switch themes. The current source, destination, and browser position are preserved across the toggle.

| Theme | Deck A accent | Deck B accent | Surfaces |
|-------|--------------|--------------|---------|
| Dark  | Cyan `#4dd0e1` | Amber `#ffb74d` | Near-black neutrals |
| Light | Avocado sage green | Terracotta / burnt orange | Warm parchment |

---

## Project structure

```
Dirtywave File Helper/
├── main.py          # entry point — creates root window and starts the app
├── state.py         # all shared mutable globals (widgets, vars, flags)
├── theme.py         # colour constants, _apply_theme_colors(), setup_styles()
├── builders.py      # all build_* UI functions, toggle_theme(), build_app()
├── browser.py       # Deck A file browser — navigation and browse dialogs
├── preview.py       # Deck B rename preview and hover tooltip
├── log_panel.py     # operation log helpers
├── operations.py    # file copy/move worker and M8 path truncation
└── constants.py     # AUDIO_EXTS, MAX_PREVIEW_ROWS
```

---

## Limitations

- Preview is capped at **500 rows** for performance; the file count still reflects the full total.
- The file browser only shows non-hidden subfolders and audio files (no other file types).
- Destination collisions are not handled — if a renamed file already exists at the target, `shutil` will overwrite it silently.
