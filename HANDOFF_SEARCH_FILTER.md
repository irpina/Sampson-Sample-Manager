# Handoff: Structured Search Filter (PLAN_SEARCH_FILTER.md)

## What to implement

See `PLAN_SEARCH_FILTER.md` for the full spec. Short version: extend the Deck B search bar to support metadata tokens (`BPM:120`, `BPM:100-130`, `Note:C`) in addition to plain filename substring search. All tokens AND together.

## Current state (as of v0.5.15)

Key detection is **already shipped** (v0.5.10). The `_preview_rows` tuple is already the full 6-tuple:

```python
(filename, renamed, subfolder, bpm_display, key_display, srcpath)
#   [0]      [1]      [2]        [3]           [4]          [5]
```

So `len(row) > 5` in the plan spec is always `True` — the `Note:` filter is fully active and should work immediately. No `if len(row) > 5` guard is needed; just use `row[4]` directly.

## Exact changes needed

### 1. `preview.py` — add `_parse_query()` above `apply_filter()`

```python
def _parse_query(text):
    """Split query into (plain_text, bpm_spec, note_spec).

    bpm_spec: None | int (exact) | (int, int) (inclusive range)
    note_spec: None | str (uppercase note name, e.g. "C", "F#")
    """
    plain_parts = []
    bpm_spec = None
    note_spec = None
    for token in text.strip().split():
        tl = token.lower()
        if tl.startswith("bpm:"):
            val = token[4:]
            if "-" in val:
                try:
                    lo, hi = val.split("-", 1)
                    bpm_spec = (int(lo), int(hi))
                except ValueError:
                    plain_parts.append(token)
            else:
                try:
                    bpm_spec = int(val)
                except ValueError:
                    plain_parts.append(token)
        elif tl.startswith("note:"):
            note_spec = token[5:].upper()
        else:
            plain_parts.append(token)
    return " ".join(plain_parts).lower(), bpm_spec, note_spec
```

### 2. `preview.py` — replace `apply_filter()`

Replace the current single-line `matched` comprehension (line 32) with a `_matches(row)` predicate. Keep everything else in `apply_filter` **exactly as-is** (the tree insert loop, count label logic, etc.).

```python
def apply_filter(text: str):
    """Show only rows matching the structured query (case-insensitive).

    Supports plain filename substring, BPM:120, BPM:100-130, Note:C tokens.
    All tokens AND together. When no filter is active, caps display at MAX_PREVIEW_ROWS.
    """
    if state.preview_tree is None:
        return
    has_query = bool(text.strip())
    plain_text, bpm_spec, note_spec = _parse_query(text)

    def _matches(row):
        orig    = row[0]
        bpm_val = row[3]
        key_val = row[4]

        if plain_text and plain_text not in orig.lower():
            return False
        if bpm_spec is not None:
            try:
                b = int(bpm_val)
            except (ValueError, TypeError):
                return False
            if isinstance(bpm_spec, tuple):
                if not (bpm_spec[0] <= b <= bpm_spec[1]):
                    return False
            elif b != bpm_spec:
                return False
        if note_spec is not None and key_val.upper() != note_spec:
            return False
        return True

    state.preview_tree.delete(*state.preview_tree.get_children())
    matched = [row for row in _preview_rows if not has_query or _matches(row)]
    display_rows = matched if has_query else matched[:constants.MAX_PREVIEW_ROWS]

    for i, (orig, renamed, subfolder, bpm_display, key_display, srcpath) in enumerate(display_rows):
        tag = "odd" if i % 2 else "even"
        state.preview_tree.insert("", "end",
                                  values=(orig, renamed, subfolder, bpm_display, key_display, srcpath),
                                  tags=(tag,))

    # Update Deck B count label — keep existing logic, just swap `query` for `has_query`
    total_cached = len(_preview_rows)
    if state.preview_count_var and total_cached > 0:
        modify_names = bool(state.modify_names_var and state.modify_names_var.get())
        n = len(matched)
        s = "s" if n != 1 else ""
        if has_query:
            state.preview_count_var.set(f"{n} of {total_cached} match")
        elif total_cached > constants.MAX_PREVIEW_ROWS:
            state.preview_count_var.set(f"Showing {constants.MAX_PREVIEW_ROWS} of {total_cached}")
        elif modify_names:
            state.preview_count_var.set(f"{total_cached} file{s} will be renamed")
        else:
            state.preview_count_var.set(f"{total_cached} audio file{s}")
```

### 3. `builders.py` — update placeholder text

Find the `CTkEntry` for the search bar in `build_deck_b()` (~line 728):

```python
# Before:
placeholder_text="Filter by filename\u2026"
# After:
placeholder_text="Filter\u2026  BPM:120  Note:C"
```

### 4. `builders.py` — version bump

Bump the version label in `build_status_bar()` to `"v0.5.16"`.

### 5. Delete this file and `PLAN_SEARCH_FILTER.md`

Once implemented and committed, delete both `HANDOFF_SEARCH_FILTER.md` and `PLAN_SEARCH_FILTER.md`.

## What NOT to touch

- `state.py` — no changes needed
- `operations.py` — no changes needed
- The tree insert loop and count label structure in `apply_filter` — keep as-is, just swap the `query`/`matched` logic
- No new dependencies

## Verification

1. `python main.py` — placeholder text reads "Filter…  BPM:120  Note:C"
2. Type `BPM:120` → only files with cached BPM = 120 shown; `???` rows excluded
3. Type `BPM:100-130` → range filter works
4. Type `kick BPM:120` → combined AND filter (filename contains "kick" AND BPM=120)
5. Type `bpm:120` (lowercase) → same result as `BPM:120`
6. Type `kick` → unchanged filename substring behavior
7. Type `Note:C` → filters by root note (works immediately, key detection already shipped)
8. Type `Note:f#` (lowercase) → same result as `Note:F#`
