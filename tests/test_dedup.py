"""Tests for duplicate detection: _DedupChecker, _find_dest_duplicates,
_dedup_dest_flat, and _gather_audio_files."""

from operations import (_DedupChecker, _dedup_dest_flat, _find_dest_duplicates,
                        _gather_audio_files)


def wav(path, content=b"RIFFxxxxWAVE"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


class TestDedupChecker:
    def test_source_to_dest_duplicate(self, tmp_path):
        dest = tmp_path / "dest"
        wav(dest / "existing.wav", b"SAME-CONTENT")
        src = wav(tmp_path / "src" / "newfile.wav", b"SAME-CONTENT")

        checker = _DedupChecker(dest, check_dest=True)
        assert checker.check(src) == "existing.wav"

    def test_different_content_not_duplicate(self, tmp_path):
        dest = tmp_path / "dest"
        wav(dest / "existing.wav", b"CONTENT-A")
        src = wav(tmp_path / "src" / "newfile.wav", b"CONTENT-B")

        checker = _DedupChecker(dest, check_dest=True)
        assert checker.check(src) is None

    def test_same_size_different_content(self, tmp_path):
        dest = tmp_path / "dest"
        wav(dest / "existing.wav", b"AAAAAAAA")
        src = wav(tmp_path / "src" / "newfile.wav", b"BBBBBBBB")

        checker = _DedupChecker(dest, check_dest=True)
        assert checker.check(src) is None

    def test_source_to_source_duplicate(self, tmp_path):
        a = wav(tmp_path / "src" / "a.wav", b"IDENTICAL")
        b = wav(tmp_path / "src" / "b.wav", b"IDENTICAL")

        checker = _DedupChecker(None, check_dest=False)
        assert checker.check(a) is None
        assert checker.check(b) == "earlier file in this run"

    def test_check_dest_false_skips_dest_comparison(self, tmp_path):
        dest = tmp_path / "dest"
        wav(dest / "existing.wav", b"SAME-CONTENT")
        src = wav(tmp_path / "src" / "newfile.wav", b"SAME-CONTENT")

        checker = _DedupChecker(dest, check_dest=False)
        assert checker.check(src) is None

    def test_missing_file_is_not_duplicate(self, tmp_path):
        checker = _DedupChecker(None, check_dest=False)
        assert checker.check(tmp_path / "ghost.wav") is None


class TestDestDuplicates:
    def test_keeps_alphabetically_first(self, tmp_path):
        wav(tmp_path / "b_copy.wav", b"DUP")
        wav(tmp_path / "a_original.wav", b"DUP")
        wav(tmp_path / "unique.wav", b"UNIQUE!!")

        dups = _find_dest_duplicates(tmp_path)
        assert len(dups) == 1
        dup_file, kept = dups[0]
        assert dup_file.name == "b_copy.wav"
        assert kept == "a_original.wav"

    def test_top_level_only(self, tmp_path):
        wav(tmp_path / "a.wav", b"DUP")
        wav(tmp_path / "sub" / "b.wav", b"DUP")
        assert _find_dest_duplicates(tmp_path) == []

    def test_dry_run_removes_nothing(self, tmp_path):
        wav(tmp_path / "a.wav", b"DUP")
        victim = wav(tmp_path / "b.wav", b"DUP")

        removed = _dedup_dest_flat(tmp_path, dry=True)
        assert removed == 1
        assert victim.exists()

    def test_real_run_removes_duplicate(self, tmp_path):
        keeper = wav(tmp_path / "a.wav", b"DUP")
        victim = wav(tmp_path / "b.wav", b"DUP")

        removed = _dedup_dest_flat(tmp_path, dry=False)
        assert removed == 1
        assert keeper.exists()
        assert not victim.exists()


class TestGatherAudioFiles:
    def test_recursive_audio_only(self, tmp_path):
        wav(tmp_path / "kit" / "kick.wav")
        wav(tmp_path / "kit" / "deep" / "sub.flac")
        (tmp_path / "kit" / "readme.txt").write_text("not audio")

        files = _gather_audio_files([str(tmp_path / "kit")])
        names = {f.name for f in files}
        assert names == {"kick.wav", "sub.flac"}

    def test_deduplicates_overlapping_selection(self, tmp_path):
        wav(tmp_path / "kit" / "kick.wav")
        files = _gather_audio_files([str(tmp_path / "kit"),
                                     str(tmp_path / "kit")])
        assert len(files) == 1

    def test_direct_file_selection(self, tmp_path):
        f = wav(tmp_path / "loop.wav")
        files = _gather_audio_files([str(f)])
        assert files == [f]

    def test_missing_path_ignored(self, tmp_path):
        assert _gather_audio_files([str(tmp_path / "ghost")]) == []
