"""Tests for the Deck B search query parser and row matcher."""

from preview import _matches_filter, _parse_query


def match(row, query):
    plain, bpm_spec, note_spec, min_len, max_len = _parse_query(query)
    return _matches_filter(row, bool(query.strip()), plain, bpm_spec,
                           note_spec, min_len, max_len)


ROW = {"src_name": "Kick_Deep_01.wav", "bpm": "120", "key": "C",
       "duration_sec": 2.5}


class TestParseQuery:
    def test_plain_text(self):
        plain, bpm, note, mn, mx = _parse_query("kick snare")
        assert plain == "kick snare"
        assert bpm is None and note is None and mn is None and mx is None

    def test_bpm_exact(self):
        assert _parse_query("BPM:120")[1] == 120

    def test_bpm_range(self):
        assert _parse_query("BPM:100-130")[1] == (100, 130)

    def test_bpm_wildcard(self):
        assert _parse_query("BPM:12*")[1] == (120, 129)

    def test_bpm_single_digit_wildcard(self):
        assert _parse_query("BPM:1*")[1] == (100, 199)

    def test_bpm_invalid_falls_back_to_plain(self):
        plain, bpm, *_ = _parse_query("BPM:abc")
        assert bpm is None
        assert "bpm:abc" in plain

    def test_note_uppercased(self):
        assert _parse_query("note:f#")[2] == "F#"

    def test_lengths(self):
        _, _, _, mn, mx = _parse_query("MinLength:10 MaxLength:90")
        assert mn == 10.0 and mx == 90.0

    def test_combined(self):
        plain, bpm, note, mn, mx = _parse_query("kick BPM:120 Note:C MaxLength:5")
        assert plain == "kick" and bpm == 120 and note == "C" and mx == 5.0


class TestMatchesFilter:
    def test_empty_query_matches_all(self):
        assert match(ROW, "")

    def test_plain_text_case_insensitive(self):
        assert match(ROW, "kick_deep")
        assert not match(ROW, "snare")

    def test_bpm_exact(self):
        assert match(ROW, "BPM:120")
        assert not match(ROW, "BPM:121")

    def test_bpm_range(self):
        assert match(ROW, "BPM:100-130")
        assert not match(ROW, "BPM:121-130")

    def test_bpm_missing_value_excluded(self):
        row = dict(ROW, bpm="")
        assert not match(row, "BPM:120")
        row = dict(ROW, bpm="???")
        assert not match(row, "BPM:120")

    def test_note(self):
        assert match(ROW, "Note:c")
        assert not match(ROW, "Note:D")

    def test_length_bounds(self):
        assert match(ROW, "MinLength:2 MaxLength:3")
        assert not match(ROW, "MinLength:3")
        assert not match(ROW, "MaxLength:2")

    def test_unknown_duration_excluded_from_length_filters(self):
        row = dict(ROW, duration_sec=None)
        assert not match(row, "MinLength:1")
        assert not match(row, "MaxLength:100")

    def test_tokens_combine_with_text(self):
        assert match(ROW, "kick BPM:120 Note:C")
        assert not match(ROW, "kick BPM:120 Note:D")
