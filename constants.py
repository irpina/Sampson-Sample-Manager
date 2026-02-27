AUDIO_EXTS       = {".wav", ".aiff", ".aif", ".flac", ".mp3", ".ogg"}
MAX_PREVIEW_ROWS = 500

# Hardware profiles — maps display name to device constraints.
# path_limit: max total path length in chars, or None for no restriction.
# To add a new device: insert one entry here. No other file needs changing.
PROFILES = {
    "Generic":    {"path_limit": None},
    "M8":         {"path_limit": 127},
    "MPC One":    {"path_limit": 255},
    "SP-404mkII": {"path_limit": 255},
}
PROFILE_NAMES = list(PROFILES.keys())
