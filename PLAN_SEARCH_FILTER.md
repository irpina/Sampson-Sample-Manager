# Plan: Structured Search for Deck B Filter

## Context

The Deck B search bar currently does a plain substring match on the original filename. Users want to filter by metadata — e.g. `BPM:170` or `Note:C` — to quickly find samples at a specific tempo or in a particular key. The plan also accounts for the future key detection column (from `PLAN_KEY_DETECTION.md`).

---

## Proposed Query Syntax

All tokens are ANDed together. Unrecognized tokens fall through to filename search.

| Token | Example | Behavior |
|-------|---------|----------|
| Plain text | `kick` | Substring match on original filename (current behavior) |
| `BPM:<n>` | `BPM:170` | Exact BPM match |
| `BPM:<lo>-<hi>` | `BPM:120-140` | BPM range (inclusive) |
| `Note:<n>` | `Note:C`, `Note:F#` | Root note match (requires key detection column) |
| Combined | `kick BPM:120-140` | Filename contains "kick" AND BPM in range |

- Token matching is case-insensitive (`bpm:120`, `BPM:120`, `Bpm:120` all work)
- `Note:` match is exact on the root label (`"C"`, `"F#"`, `"Bb"`) — case-insensitive
- `BPM:"???"` or `BPM:""` rows never match a BPM filter (detection not run yet)
- `Note:` filter silently passes all rows if the key column doesn't exist yet

---

## Implementation — 2 files only

### `preview.py`

**Add `_parse_query(text)`** (private helper, above `apply_filter`):

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

**Replace `apply_filter(text)`** — swap the single-line `matched` list comprehension with a `_matches(row)` predicate that applies all three filter components:

```python
def apply_filter(text: str):
    has_query = bool(text.strip())
    plain_text, bpm_spec, note_spec = _parse_query(text)

    def _matches(row):
        orig       = row[0]
        bpm_val    = row[3]
        key_val    = row[4] if len(row) > 5 else ""  # key column added by PLAN_KEY_DETECTION.md

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

    matched = [row for row in _preview_rows if not has_query or _matches(row)]
    display_rows = matched if has_query else matched[:constants.MAX_PREVIEW_ROWS]
    # ... insert rows and update count label unchanged
```

**Count label** — the existing `if query:` branch already uses `text.strip()` implicitly; no change needed since `has_query` maps to the same condition.

### `builders.py`

Update the `placeholder_text` of the `CTkEntry` search bar (line ~661):

```python
# before:
placeholder_text="Filter by filename\u2026"
# after:
placeholder_text="Filter\u2026 or BPM:120 or Note:C"
```

---

## Files to modify

| File | Change |
|------|--------|
| `preview.py` | Add `_parse_query()`, refactor `apply_filter()` with `_matches()` predicate |
| `builders.py` | Update search bar placeholder text; version bump → `"v0.5.10"` |

---

## Notes

- **No state changes** — `preview_filter_var` is already a StringVar and the trace fires on every keystroke.
- **No new dependencies**.
- **`Note:` filter** is designed now, active only after `PLAN_KEY_DETECTION.md` is implemented (adds `key_display` at row index 4, shifting srcpath to index 5). Until then, `len(row) > 5` is False so `Note:` always passes.
- **BPM range tolerance**: exact integer match only. If users want ±5 BPM fuzzy matching, that's a future extension.

---

## Verification

1. `python main.py` — placeholder text reads "Filter… or BPM:120 or Note:C"
2. Type `BPM:120` → only files with cached BPM = 120 shown; `"???"` rows excluded
3. Type `BPM:100-130` → range filter works
4. Type `kick BPM:120` → combined AND filter works
5. Type `bpm:120` (lowercase) → same result as `BPM:120`
6. Type `kick` → unchanged filename substring behavior
7. After key detection is implemented: `Note:C` filters by root note
