"""
Layout / width / wrapping regression tests for Femto.

Covers: ASCII regression (PR #8), wide CJK characters (PR #8),
ZWJ clusters & variation selectors (PR #24), combining marks (PR #28),
and word-boundary wrapping (v0.0.3a03).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from femto.layout import (
    char_width,
    str_width,
    chunk_line,
    line_row_count,
    get_visual_position,
    get_logical_from_visual,
    col_to_index,
    get_logical_from_visual_point,
)

FAMILY = "\U0001F468\u200D\U0001F469\u200D\U0001F467\u200D\U0001F466"  # 👨👩‍‍
E_COMBINING = "e\u0301"          # e + combining acute
N_COMBINING = "n\u0303"          # n + combining tilde


class TestCharWidth(unittest.TestCase):
    def test_ascii(self):
        self.assertEqual(char_width("a"), 1)
        self.assertEqual(char_width(" "), 1)

    def test_wide_cjk(self):
        self.assertEqual(char_width("漢"), 2)
        self.assertEqual(char_width("字"), 2)

    def test_combining_zero(self):
        self.assertEqual(char_width("\u0301"), 0)
        self.assertEqual(char_width("\u0303"), 0)

    def test_vs16_zero(self):
        self.assertEqual(char_width("\uFE0F"), 0)

    def test_zwj_zero(self):
        self.assertEqual(char_width("\u200D"), 0)


class TestStrWidth(unittest.TestCase):
    def test_ascii(self):
        self.assertEqual(str_width("hello"), 5)

    def test_cjk(self):
        self.assertEqual(str_width("漢字"), 4)

    def test_combining_counts_once(self):
        self.assertEqual(str_width(E_COMBINING), 1)
        self.assertEqual(str_width(N_COMBINING), 1)

    def test_zwj_cluster_counts_once(self):
        self.assertEqual(str_width(FAMILY), 2)

    def test_mixed(self):
        self.assertEqual(str_width("a漢b"), 4)


class TestChunkLineAscii(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(chunk_line("", 5), [""])

    def test_exact_width(self):
        self.assertEqual(chunk_line("abcde", 5), ["abcde"])

    def test_hard_cut_no_spaces(self):
        self.assertEqual(chunk_line("abcdefg", 3), ["abc", "def", "g"])

    def test_word_boundary(self):
        chunks = chunk_line("hello world this is a test", 12)
        self.assertEqual(chunks[0], "hello world ")
        self.assertEqual(len(chunks), 3)

    def test_hard_cut_fallback_long_word(self):
        chunks = chunk_line("supercalifragilisticexpialidocious", 10)
        self.assertEqual(chunks[0], "supercalif")

    def test_short_line_single_chunk(self):
        self.assertEqual(chunk_line("short", 20), ["short"])


class TestChunkLineWide(unittest.TestCase):
    def test_wide_chars_not_split(self):
        self.assertEqual(chunk_line("漢字漢字", 4), ["漢字", "漢字"])

    def test_odd_width_no_split(self):
        self.assertEqual(chunk_line("漢字漢字", 5), ["漢字", "漢字"])


class TestVisualWide(unittest.TestCase):
    def test_visual_position_wide(self):
        # char index 3 = second char of second row -> display col 2
        vx, vy = get_visual_position(3, 0, ["漢字漢字"], 4)
        self.assertEqual((vx, vy), (2, 1))

    def test_visual_position_line_end_wrap(self):
        vx, vy = get_visual_position(10, 0, ["0123456789"], 10)
        self.assertEqual((vx, vy), (0, 1))

    def test_logical_roundtrip_wide(self):
        lines = ["漢字漢字漢字"]
        vx, vy = get_visual_position(2, 0, lines, 4)
        self.assertEqual(get_logical_from_visual(vy, lines, 4), 0)


class TestCombiningCursor(unittest.TestCase):
    def test_col_to_index_skips_combining(self):
        self.assertEqual(col_to_index(E_COMBINING + "x", 1), 2)

    def test_col_to_index_wide_mid_char(self):
        self.assertEqual(col_to_index("漢字", 3), 1)

    def test_col_to_index_beyond(self):
        self.assertEqual(col_to_index("ab", 99), 2)


class TestMouseMapping(unittest.TestCase):
    def test_visual_point_roundtrip(self):
        lines = ["0123456789ABCDE"]
        x, y = get_logical_from_visual_point(1, 2, lines, 10)
        self.assertEqual((x, y), (12, 0))

    def test_visual_point_wide(self):
        lines = ["漢字漢字"]
        x, y = get_logical_from_visual_point(1, 0, lines, 4)
        self.assertEqual((x, y), (2, 0))

    def test_visual_point_beyond_eof(self):
        x, y = get_logical_from_visual_point(99, 99, ["ab", "cd"], 80)
        self.assertEqual((x, y), (2, 1))

    def test_hard_wrap_identity(self):
        self.assertEqual(
            get_logical_from_visual_point(4, 7, ["ab"], 80, soft_wrap=False),
            (7, 4))


class TestRowCount(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(line_row_count(0, 10), 1)

    def test_exact(self):
        self.assertEqual(line_row_count(10, 10), 1)

    def test_overflow(self):
        self.assertEqual(line_row_count(11, 10), 2)


if __name__ == "__main__":
    unittest.main()
