AUDIO_EXTS       = {".wav", ".aiff", ".aif", ".flac", ".mp3", ".ogg"}
MAX_PREVIEW_ROWS = 500

# Hardware profiles — maps display name to device constraints.
# path_limit: max total path length in chars, or None for no restriction.
# conversion: dict of audio conversion settings, or None for no conversion.
#
# To add a new device: insert one entry here. No other file needs changing.
PROFILES = {
    "Generic": {
        "path_limit": None,
        "conversion": None,  # No auto-conversion
    },
    "M8": {
        "path_limit": 127,
        "conversion": {
            "format": "wav",
            "sample_rate": 44100,
            "bit_depth": 16,
            "channels": None,  # Keep original
            "normalize": False,
        }
    },
    "MPC One": {
        "path_limit": 255,
        "conversion": None,  # User choice - MPC supports many formats
    },
    "SP-404mkII": {
        "path_limit": 255,
        "conversion": None,  # User choice
    },
    "Elektron Digitakt": {
        "path_limit": None,
        "conversion": {
            "format": "wav",
            "sample_rate": 48000,
            "bit_depth": 16,
            "channels": 1,  # Force mono - Digitakt requirement
            "normalize": False,
        }
    },
    "Elektron Analog Rytm": {
        "path_limit": None,
        "conversion": {
            "format": "wav",
            "sample_rate": 48000,
            "bit_depth": 16,
            "channels": None,  # Keep original
            "normalize": False,
        }
    },
    "Elektron Syntakt": {
        "path_limit": None,
        "conversion": {
            "format": "wav",
            "sample_rate": 48000,
            "bit_depth": 16,
            "channels": None,
            "normalize": False,
        }
    },
}
PROFILE_NAMES = list(PROFILES.keys())
