AUDIO_EXTS       = {".wav", ".aiff", ".aif", ".flac", ".mp3", ".ogg"}
MAX_PREVIEW_ROWS = 500
MIN_BPM_DURATION_MS = 3000  # Skip BPM detection on files shorter than this

# Hardware profiles — maps display name to device constraints.
# path_limit: max total path length in chars, or None for no restriction.
# conversion: dict of audio conversion settings, or None for no conversion.
#
# To add a new device: insert one entry here AND add the option to ui/index.html.
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
    "Akai MPC Sample": {
        "path_limit": 255,
        "conversion": None,  # Multi-format: WAV, AIFF, MP3, FLAC, OGG — user choice
    },
    "TE EP-133 K.O. II": {
        "path_limit": None,
        "conversion": {
            "format": "wav",
            "sample_rate": 44100,  # Native is 46875Hz; device accepts lower rates as-is
            "bit_depth": 16,
            "channels": None,  # Keep original stereo/mono
            "normalize": False,
        }
        # Note: 20-second max sample length per slot on device
    },
}
PROFILE_NAMES = list(PROFILES.keys())
