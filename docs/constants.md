# constants.py — Hardware Profiles & Audio Formats

Config-only module. No imports, no logic.

## Imports
- **Imports:** nothing
- **Imported by:** `browser`, `preview`, `operations`, `api`

## Exports

### `AUDIO_EXTS`
```python
{".wav", ".aiff", ".aif", ".flac", ".mp3", ".ogg"}
```
Input formats accepted by the file browser and operations worker.

### `MAX_PREVIEW_ROWS`
```python
500
```
Maximum rows shown in Deck B when no filter is active. Filter bypasses this cap (all matches shown).

### `PROFILES`
Hardware device profiles. Each entry:

| Key | Type | Description |
|-----|------|-------------|
| `path_limit` | `int \| None` | Max full destination path length in chars; `None` = no limit |
| `conversion` | `dict \| None` | Auto-conversion preset; `None` = no auto-conversion |

Current profiles:

| Device | Path Limit | Auto-Convert |
|--------|-----------|-------------|
| Generic | None | None |
| M8 | 127 | 44.1kHz / 16-bit / WAV |
| MPC One | 255 | None |
| SP-404mkII | 255 | None |
| Elektron Digitakt | None | 48kHz / 16-bit / mono WAV |
| Elektron Analog Rytm | None | 48kHz / 16-bit / WAV |
| Elektron Syntakt | None | 48kHz / 16-bit / WAV |

Conversion dict keys: `format`, `sample_rate`, `bit_depth`, `channels` (1=mono, 2=stereo, None=keep), `normalize`

### `PROFILE_NAMES`
List of all profile keys in display order.

## Adding a New Device

Insert one entry into `PROFILES` — nothing else in the codebase needs changing. The UI, operations worker, and preview all read `PROFILES` dynamically.

---
*SAMPSON is licensed under the [GNU General Public License v3.0](../LICENSE).*
