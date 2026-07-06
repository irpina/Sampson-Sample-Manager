"""Tests for _compute_output and _apply_path_limit — the single source of
truth for output filenames, shared by preview, run, and sync."""

from pathlib import Path

from operations import _apply_path_limit, _compute_output


# Literal paths, never resolved — keeps path-length assertions deterministic
# on both Windows and POSIX CI runners.
SRC = Path("C:/lib")
DEST = Path("C:/dest")


def compute(f, **kw):
    defaults = dict(source_root=SRC, dest=DEST, no_rename=False,
                    struct_mode="flat", path_limit=None)
    defaults.update(kw)
    return _compute_output(Path(f), **defaults)


class TestFilename:
    def test_parent_prefix_default(self):
        name, sub = compute(SRC / "Kicks" / "kick_01.wav")
        assert name == "Kicks_kick_01.wav"
        assert sub == ""

    def test_keep_original_names(self):
        name, _ = compute(SRC / "Kicks" / "kick_01.wav", no_rename=True)
        assert name == "kick_01.wav"

    def test_custom_prefix_overrides_parent(self):
        name, _ = compute(SRC / "Kicks" / "kick_01.wav", custom_prefix="KIT")
        assert name == "KIT_kick_01.wav"

    def test_custom_prefix_wins_even_with_no_rename(self):
        name, _ = compute(SRC / "Kicks" / "kick_01.wav", no_rename=True,
                          custom_prefix="KIT")
        assert name == "KIT_kick_01.wav"


class TestSubfolder:
    def test_flat_mode_no_subfolder(self):
        _, sub = compute(SRC / "Drums" / "Kicks" / "k.wav", struct_mode="flat")
        assert sub == ""

    def test_mirror_mode_preserves_tree(self):
        _, sub = compute(SRC / "Drums" / "Kicks" / "k.wav", struct_mode="mirror")
        assert Path(sub) == Path("Drums/Kicks")

    def test_mirror_mode_root_file(self):
        _, sub = compute(SRC / "k.wav", struct_mode="mirror")
        assert sub == ""

    def test_mirror_mode_outside_root(self):
        # File outside source_root: relative_to fails, falls back to flat
        _, sub = compute(Path("C:/elsewhere/k.wav"), struct_mode="mirror")
        assert sub == ""

    def test_parent_mode_uses_immediate_parent(self):
        _, sub = compute(SRC / "Drums" / "Kicks" / "k.wav", struct_mode="parent")
        assert sub == "Kicks"

    def test_parent_mode_root_file(self):
        _, sub = compute(SRC / "k.wav", struct_mode="parent")
        assert sub == ""


class TestSuffixes:
    def test_bpm_suffix(self):
        name, _ = compute(SRC / "Loops" / "loop.wav", bpm=120.4, append_bpm=True)
        assert name == "Loops_loop_120bpm.wav"

    def test_bpm_rounds(self):
        name, _ = compute(SRC / "Loops" / "loop.wav", bpm=119.7, append_bpm=True)
        assert name == "Loops_loop_120bpm.wav"

    def test_key_suffix(self):
        name, _ = compute(SRC / "Bass" / "bass.wav", key="F#", append_key=True)
        assert name == "Bass_bass_F#.wav"

    def test_bpm_and_key_suffix_order(self):
        name, _ = compute(SRC / "Loops" / "loop.wav",
                          bpm=90, append_bpm=True, key="C", append_key=True)
        assert name == "Loops_loop_90bpm_C.wav"

    def test_no_suffix_when_value_missing(self):
        name, _ = compute(SRC / "Loops" / "loop.wav", bpm=None, append_bpm=True)
        assert name == "Loops_loop.wav"


class TestPathLimit:
    def test_no_truncation_when_under_limit(self):
        assert _apply_path_limit("short.wav", str(DEST), 260) == "short.wav"

    def test_truncates_to_limit(self):
        long_name = "x" * 300 + ".wav"
        out = _apply_path_limit(long_name, str(DEST), 127)
        assert len(str(DEST / out)) <= 127
        assert out.endswith(".wav")

    def test_protected_suffixes_survive_truncation(self):
        long_name = "y" * 300 + "_120bpm_C.wav"
        out = _apply_path_limit(long_name, str(DEST), 127,
                                protect_suffixes=["_120bpm", "_C"])
        assert out.endswith("_120bpm_C.wav")
        assert len(str(DEST / out)) <= 127

    def test_extension_always_preserved(self):
        out = _apply_path_limit("z" * 300 + ".aif", str(DEST), 40)
        assert out.endswith(".aif")

    def test_via_compute_output(self):
        name, _ = compute(SRC / ("Folder" + "a" * 100) / ("file" + "b" * 100 + ".wav"),
                          path_limit=127)
        assert len(str(DEST / name)) <= 127
        assert name.endswith(".wav")
