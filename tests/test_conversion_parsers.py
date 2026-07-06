"""Tests for the conversion dropdown-value parsers."""

from conversion import (get_target_extension, parse_bit_depth,
                        parse_channels, parse_sample_rate)


class TestSampleRate:
    def test_keep(self):
        assert parse_sample_rate("keep") is None
        assert parse_sample_rate("Keep original") is None
        assert parse_sample_rate("") is None

    def test_k_notation(self):
        assert parse_sample_rate("44.1k") == 44100
        assert parse_sample_rate("48k") == 48000
        assert parse_sample_rate("96k") == 96000

    def test_raw_number(self):
        assert parse_sample_rate("44100") == 44100


class TestBitDepth:
    def test_keep(self):
        assert parse_bit_depth("keep") is None

    def test_bit_notation(self):
        assert parse_bit_depth("16bit") == 16
        assert parse_bit_depth("24bit") == 24
        assert parse_bit_depth("32bit") == 32


class TestChannels:
    def test_keep(self):
        assert parse_channels("keep") is None

    def test_words_and_numbers(self):
        assert parse_channels("mono") == 1
        assert parse_channels("stereo") == 2
        assert parse_channels("1") == 1
        assert parse_channels("2") == 2

    def test_unknown_is_none(self):
        assert parse_channels("5.1") is None


class TestTargetExtension:
    def test_wav(self):
        assert get_target_extension("wav") == ".wav"
        assert get_target_extension("WAV") == ".wav"

    def test_aiff_maps_to_aif(self):
        assert get_target_extension("aiff") == ".aif"
        assert get_target_extension("aif") == ".aif"

    def test_unknown_defaults_to_wav(self):
        assert get_target_extension("flac") == ".wav"
