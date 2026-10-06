"""Regression tests for line-spanning Python syntax highlighting."""

import unittest
from unittest.mock import MagicMock, patch

from femto.app import Application
from femto.buffer import Buffer
from femto.config import Config
from femto.cursor import Cursor
from femto.renderer import Renderer


class TestRendererHighlighting(unittest.TestCase):
    def setUp(self):
        self.config = Config()
        self.config.show_line_numbers = False
        self.screen = MagicMock()
        self.screen.getmaxyx.return_value = (6, 80)
        with patch.object(Renderer, 'setup_colors'):
            self.renderer = Renderer(self.screen, self.config)
        self.renderer._draw_chunk = MagicMock()
        self.buffer = Buffer(self.config)
        self.buffer.filename = 'example.py'
        self.cursor = Cursor()

    def draw(self, scroll_y=0, rows=4, cols=80):
        self.cursor.scroll_y = scroll_y
        self.renderer._draw_chunk.reset_mock()
        self.renderer.draw_text(self.buffer, self.cursor, rows, cols)
        return {call.args[3]: call.args[7]
                for call in self.renderer._draw_chunk.call_args_list}

    def test_docstring_body_and_code_after_close(self):
        for delimiter in ('"""', "'''"):
            for soft_wrap in (False, True):
                with self.subTest(delimiter=delimiter, soft_wrap=soft_wrap):
                    self.config.soft_wrap = soft_wrap
                    self.buffer.lines = [delimiter, 'def class return',
                                         delimiter, 'return 42']
                    spans = self.draw()
                    self.assertEqual(spans[1], [(0, 16, 4)])
                    self.assertEqual(spans[3], [(0, 6, 5), (7, 9, 6)])

    def test_first_draw_starts_inside_offscreen_string(self):
        for soft_wrap in (False, True):
            with self.subTest(soft_wrap=soft_wrap):
                self.config.soft_wrap = soft_wrap
                self.buffer.lines = ['"""', 'class return', '"""']
                self.assertEqual(self.draw(1, 1)[1], [(0, 12, 4)])

    def test_wrapped_string_offsets(self):
        self.config.soft_wrap = True
        self.config.wrap_at_word = False
        self.buffer.lines = ['"""', 'def class return', '"""']
        self.draw(2, 2, 8)
        calls = self.renderer._draw_chunk.call_args_list
        self.assertEqual(calls[0].args[1:4], ('s return', 8, 1))
        self.assertEqual(calls[0].args[7], [(0, 16, 4)])

    def test_word_wrapped_string_offsets_with_offscreen_opening(self):
        self.config.soft_wrap = True
        self.config.wrap_at_word = True
        for delimiter in ('"""', "'''"):
            with self.subTest(delimiter=delimiter):
                self.buffer.lines = [delimiter, 'def class return', delimiter]
                self.draw(2, 2, 8)
                calls = self.renderer._draw_chunk.call_args_list
                self.assertEqual(calls[0].args[1:4], ('class ', 4, 1))
                self.assertEqual(calls[1].args[1:4], ('return', 10, 1))
                for call in calls:
                    self.assertEqual(call.args[7], [(0, 16, 4)])

    def test_search_and_selection_overlays_preserve_priority_in_string(self):
        self.config.soft_wrap = False
        self.buffer.lines = ['"""', 'return 42', '"""']
        self.cursor.scroll_y = 1
        self.renderer.all_match_attr = 40
        self.renderer.match_attr = 50
        self.renderer.sel_attr = 60
        self.renderer._draw_chunk = Renderer._draw_chunk.__get__(self.renderer)
        cells = {}

        def write(row, col, text, attr=0):
            for offset, char in enumerate(text):
                cells[col + offset] = (char, attr)

        self.screen.addstr.side_effect = write
        with patch('femto.renderer.curses.color_pair', side_effect=lambda n: n):
            self.renderer.draw_text(
                self.buffer, self.cursor, 1, 9,
                sel=((4, 1), (5, 1)), match=(3, 1, 3),
                all_matches=[(1, 1, 7)])
        self.assertEqual(''.join(cells[x][0] for x in range(9)), 'return 42')
        self.assertEqual([cells[x][1] for x in range(9)],
                         [4, 40, 40, 50, 60, 50, 40, 40, 4])

    def test_edit_opening_delimiter_updates_following_lines(self):
        self.buffer.lines = ['"""', 'return', '"""', 'return']
        self.assertEqual(self.draw()[1], [(0, 6, 4)])
        self.buffer.delete_char(0, 0)
        spans = self.draw()
        self.assertEqual(spans[1], [(0, 6, 5)])
        self.assertEqual(spans[3], [(0, 6, 4)])
        self.buffer.insert_char(0, 0, '"')
        self.assertEqual(self.draw()[3], [(0, 6, 5)])

    def test_edit_closing_delimiter_updates_following_lines(self):
        self.buffer.lines = ['"""', 'return', '"""', 'return']
        self.draw()
        self.buffer.delete_char(0, 2)
        self.assertEqual(self.draw()[3], [(0, 6, 4)])
        self.buffer.insert_char(0, 2, '"')
        self.assertEqual(self.draw()[3], [(0, 6, 5)])

    def test_undo_redo_uses_updated_state(self):
        app = Application()
        app.buffer.filename = 'example.py'
        app.buffer.lines = ['"""', 'return', '"""', 'return']
        self.buffer = app.buffer
        app._snapshot()
        app.buffer.delete_char(0, 0)
        self.assertEqual(self.draw()[1], [(0, 6, 5)])
        app._do_undo()
        self.assertEqual(self.draw()[1], [(0, 6, 4)])
        app._do_redo()
        self.assertEqual(self.draw()[1], [(0, 6, 5)])

    def test_same_revision_buffers_redraw_and_keep_separate_states(self):
        self.buffer.lines = ['"""', 'return', '"""']
        self.cursor.scroll_y = 1
        self.renderer.render(self.buffer, self.cursor)
        self.assertEqual(self.renderer._draw_chunk.call_args_list[0].args[7],
                         [(0, 6, 4)])
        other = Buffer(self.config)
        other.filename = 'example.py'
        other.lines = ['', 'return', '']
        self.renderer._draw_chunk.reset_mock()
        self.renderer.render(other, self.cursor)
        self.assertTrue(self.renderer._draw_chunk.called)
        self.assertEqual(self.renderer._draw_chunk.call_args_list[0].args[7],
                         [(0, 6, 5)])
        self.buffer = other
        self.assertEqual(self.draw(1, 1)[1], [(0, 6, 5)])

    def test_non_python_and_disabled_highlighting(self):
        self.buffer.lines = ['"""', 'return']
        self.buffer.filename = 'example.js'
        self.assertEqual(self.draw()[1], [])
        self.buffer.filename = 'example.py'
        self.config.syntax_highlight = False
        self.assertEqual(self.draw()[1], [])


    def test_buffer_switch_preserves_unchanged_cached_prefix(self):
        self.buffer.lines = ['"""', 'return']
        self.draw(1, 1)
        first = self.buffer
        self.buffer = Buffer(self.config)
        self.buffer.filename = 'other.py'
        self.buffer.lines = ['', 'return']
        self.assertEqual(self.draw(1, 1)[1], [(0, 6, 5)])
        self.buffer = first
        with patch('femto.highlight.highlight_line') as process:
            self.assertEqual(self.draw(1, 1)[1], [(0, 6, 4)])
            process.assert_not_called()

    def test_frame_redraws_for_highlighting_and_filename_changes(self):
        self.buffer.lines = ['"""', 'return']
        self.cursor.scroll_y = 1
        self.renderer.render(self.buffer, self.cursor)
        self.renderer._draw_chunk.reset_mock()
        self.renderer.render(self.buffer, self.cursor)
        self.renderer._draw_chunk.assert_not_called()
        self.config.syntax_highlight = False
        self.renderer.render(self.buffer, self.cursor)
        self.assertEqual(
            self.renderer._draw_chunk.call_args_list[0].args[7], [])
        self.config.syntax_highlight = True
        self.buffer.filename = 'other.txt'
        self.renderer._draw_chunk.reset_mock()
        self.renderer.render(self.buffer, self.cursor)
        self.assertEqual(
            self.renderer._draw_chunk.call_args_list[0].args[7], [])
        self.buffer.filename = 'other.py'
        self.renderer._draw_chunk.reset_mock()
        self.renderer.render(self.buffer, self.cursor)
        self.assertEqual(self.renderer._draw_chunk.call_args_list[0].args[7],
                         [(0, 6, 4)])

    def test_discarded_buffers_release_their_highlight_cache(self):
        import gc
        import weakref
        temporary = Buffer(self.config)
        temporary.filename = 'temporary.py'
        temporary.lines = ['return']
        self.renderer._highlights_for(temporary, 0)
        reference = weakref.ref(temporary)
        del temporary
        gc.collect()
        self.assertIsNone(reference())
        self.assertEqual(len(self.renderer._highlight_caches), 0)

    def test_frame_redraws_when_word_wrapping_changes(self):
        self.config.soft_wrap = True
        self.config.wrap_at_word = True
        self.screen.getmaxyx.return_value = (6, 8)
        self.buffer.lines = ['"""', 'def class return', '"""']
        self.cursor.scroll_y = 1
        self.renderer.render(self.buffer, self.cursor)
        self.assertEqual(self.renderer._draw_chunk.call_args_list[0].args[1:4],
                         ('def ', 0, 1))
        self.renderer._draw_chunk.reset_mock()
        self.renderer.render(self.buffer, self.cursor)
        self.renderer._draw_chunk.assert_not_called()
        self.config.wrap_at_word = False
        self.renderer.render(self.buffer, self.cursor)
        self.assertEqual(self.renderer._draw_chunk.call_args_list[0].args[1:4],
                         ('def clas', 0, 1))
        self.assertEqual(self.renderer._draw_chunk.call_args_list[0].args[7],
                         [(0, 16, 4)])


    def test_pasting_delimiter_updates_cached_state(self):
        app = Application()
        app.buffer.filename = 'example.py'
        app.buffer.lines = ['', 'return', '']
        self.buffer = app.buffer
        self.assertEqual(self.draw()[1], [(0, 6, 5)])
        app.clipboard.store('"""')
        app._paste()
        self.assertEqual(self.draw()[1], [(0, 6, 4)])
        app._do_undo()
        self.assertEqual(self.draw()[1], [(0, 6, 5)])
        app._do_redo()
        self.assertEqual(self.draw()[1], [(0, 6, 4)])

    def test_cutting_selected_delimiter_updates_cached_state(self):
        app = Application()
        app.buffer.filename = 'example.py'
        app.buffer.lines = ['"""', 'return', '"""']
        self.buffer = app.buffer
        self.assertEqual(self.draw()[1], [(0, 6, 4)])
        app.selection.toggle(0, 0)
        app.cursor.x = 3
        app._cut()
        self.assertEqual(self.draw()[1], [(0, 6, 5)])
        app._do_undo()
        self.assertEqual(self.draw()[1], [(0, 6, 4)])
        app._do_redo()
        self.assertEqual(self.draw()[1], [(0, 6, 5)])

    def test_continued_ordinary_strings_preserve_following_code(self):
        for quote, apparent in (('"', "'''"), ("'", '"""')):
            for prefix in ('', 'r', 'b', 'u', 'f'):
                for wrap in (False, True):
                    with self.subTest(quote=quote, prefix=prefix, wrap=wrap):
                        self.config.soft_wrap = wrap
                        self.buffer.lines = [
                            'value = ' + prefix + quote + '\\',
                            apparent + quote, 'answer = 42',
                            'def example():', '    return 7']
                        compile('\n'.join(self.buffer.lines) + '\n',
                                'continued.py', 'exec')
                        spans = self.draw(rows=5)
                        self.assertEqual(spans[2], [(9, 11, 6)])
                        self.assertEqual(spans[3], [(0, 3, 5)])
                        self.assertEqual(spans[4],
                                         [(4, 10, 5), (11, 12, 6)])

    def test_first_viewport_after_continued_string_close(self):
        for quote, apparent in (('"', "'''"), ("'", '"""')):
            for wrap in (False, True):
                with self.subTest(quote=quote, wrap=wrap):
                    self.config.soft_wrap = wrap
                    self.buffer.lines = ['value = ' + quote + '\\',
                                         apparent + quote, 'answer = 42',
                                         'def example():', '    return 7']
                    spans = self.draw(2, rows=3)
                    self.assertEqual(spans[2], [(9, 11, 6)])
                    self.assertEqual(spans[3], [(0, 3, 5)])
                    self.assertEqual(spans[4], [(4, 10, 5), (11, 12, 6)])

    def test_editing_continuation_updates_offscreen_context(self):
        for quote, apparent in (('"', "'''"), ("'", '"""')):
            with self.subTest(quote=quote):
                self.buffer.lines = ['value = ' + quote + '\\',
                                     apparent + quote, 'answer = 42']
                self.assertEqual(self.draw(2, 1)[2], [(9, 11, 6)])
                self.buffer.delete_char(9, 0)
                self.assertEqual(self.draw(2, 1)[2], [(0, 11, 4)])
                self.buffer.insert_char(9, 0, '\\')
                self.assertEqual(self.draw(2, 1)[2], [(9, 11, 6)])




class TestLineHighlighting(unittest.TestCase):
    def setUp(self):
        from femto import highlight
        self.highlight = highlight
        highlight._CACHE.clear()

    def test_both_delimiters_same_line(self):
        for delimiter in ('"""', "'''"):
            line = delimiter + 'def class return' + delimiter
            spans, state = self.highlight.highlight_line(line)
            self.assertEqual(spans, [(0, len(line), 4)])
            self.assertIsNone(state)

    def test_open_empty_continue_and_close(self):
        for delimiter in ('"""', "'''"):
            spans, state = self.highlight.highlight_line(delimiter)
            self.assertEqual(spans, [(0, 3, 4)])
            self.assertEqual(state, delimiter)
            self.assertEqual(self.highlight.highlight_line('', state),
                             ([], delimiter))
            self.assertEqual(self.highlight.highlight_line('class', state),
                             ([(0, 5, 4)], delimiter))
            self.assertEqual(self.highlight.highlight_line(delimiter, state),
                             ([(0, 3, 4)], None))

    def test_code_before_open_and_after_close(self):
        for delimiter in ('"""', "'''"):
            line = ('return 1; ' + delimiter + 'class' + delimiter
                    + '; return 2')
            spans, state = self.highlight.highlight_line(line)
            self.assertEqual(spans, [(0, 6, 5), (7, 8, 6), (10, 21, 4),
                                     (23, 29, 5), (30, 31, 6)])
            self.assertIsNone(state)
            self.assertEqual(self.highlight.highlight_line(
                'return ' + delimiter + 'class'),
                ([(0, 6, 5), (7, 15, 4)], delimiter))

    def test_closing_then_reopening_on_one_line(self):
        self.assertEqual(self.highlight.highlight_line(
            '""" if 1: """next', '"""'),
            ([(0, 3, 4), (4, 6, 5), (7, 8, 6), (10, 17, 4)], '"""'))

    def test_opposite_quotes_and_comments_inside_string(self):
        pairs = (('"""', "'''"), ("'''", '"""'))
        for delimiter, opposite in pairs:
            line = opposite + ' # def return 99'
            self.assertEqual(self.highlight.highlight_line(line, delimiter),
                             ([(0, len(line), 4)], delimiter))

    def test_escaped_triple_delimiter_does_not_close(self):
        for delimiter in ('"""', "'''"):
            line = '\\' + delimiter + ' return'
            self.assertEqual(self.highlight.highlight_line(line, delimiter),
                             ([(0, len(line), 4)], delimiter))
            line = delimiter + '\\' + delimiter + ' def ' + delimiter
            self.assertEqual(self.highlight.highlight_line(line),
                             ([(0, len(line), 4)], None))

    def test_even_backslashes_allow_closing(self):
        for delimiter in ('"""', "'''"):
            line = '\\\\' + delimiter + ' return'
            self.assertEqual(self.highlight.highlight_line(line, delimiter),
                             ([(0, 5, 4), (6, 12, 5)], None))

    def test_delimiters_inside_comments_do_not_open(self):
        for delimiter in ('"""', "'''"):
            line = 'return 1 # ' + delimiter
            self.assertEqual(self.highlight.highlight_line(line),
                             ([(0, 6, 5), (7, 8, 6), (9, 14, 3)], None))

    def test_delimiters_inside_ordinary_strings_do_not_open(self):
        for quote, delimiter in (("'", '"""'), ('"', "'''")):
            line = quote + delimiter + ' def return' + quote
            self.assertEqual(self.highlight.highlight_line(line),
                             ([(0, len(line), 4)], None))

    def test_ordinary_strings_escaped_quotes_and_other_tokens(self):
        for line in (r'"say \"def\""', r"'say \'class\''"):
            self.assertEqual(self.highlight.highlight_line(line),
                             ([(0, len(line), 4)], None))
        line = 'def f(): return "class" # 123'
        self.assertEqual(self.highlight.get_spans(line),
                         [(0, 3, 5), (9, 15, 5), (16, 23, 4), (24, 29, 3)])
        self.assertEqual(self.highlight.get_spans('value = 12.5'),
                         [(8, 12, 6)])

    def test_existing_prefix_behavior_is_preserved(self):
        for prefix in ('r', 'b', 'u', 'f', 'R', 'br', 'rf'):
            for delimiter in ('"""', "'''"):
                line = prefix + delimiter + 'return' + delimiter
                self.assertEqual(self.highlight.highlight_line(line),
                                 ([(len(prefix), len(line), 4)], None))
                self.assertEqual(self.highlight.highlight_line(
                    prefix + delimiter),
                    ([(len(prefix), len(prefix) + 3, 4)], delimiter))

    def test_cache_distinguishes_entering_states(self):
        line = 'return 1'
        code = self.highlight.highlight_line(line)
        double = self.highlight.highlight_line(line, '"""')
        single = self.highlight.highlight_line(line, "'''")
        self.assertEqual(code, ([(0, 6, 5), (7, 8, 6)], None))
        self.assertEqual(double, ([(0, 8, 4)], '"""'))
        self.assertEqual(single, ([(0, 8, 4)], "'''"))
        cases = ((None, code), ('"""', double), ("'''", single))
        for state, expected in cases:
            self.assertIs(self.highlight.highlight_line(line, state), expected)

    def test_cache_eviction_keeps_state_correct(self):
        with patch.object(self.highlight, '_CACHE_MAX', 2):
            self.highlight.highlight_line('return')
            self.highlight.highlight_line('return', '"""')
            self.highlight.highlight_line('class')
            self.assertLessEqual(len(self.highlight._CACHE), 2)
            self.assertEqual(self.highlight.highlight_line('return', '"""'),
                             ([(0, 6, 4)], '"""'))


class TestBufferHighlightCache(unittest.TestCase):
    def setUp(self):
        from femto.highlight import HighlightCache
        self.cache = HighlightCache()
        self.buffer = Buffer(Config())
        self.buffer.lines = ['"""', '', 'return', '"""', 'return']

    def test_jump_directly_to_middle_then_after_close(self):
        self.assertEqual(self.cache.get_spans(self.buffer, 2), [(0, 6, 4)])
        self.assertEqual(self.cache.get_spans(self.buffer, 4),
                         [(0, 6, 5)])

    def test_unchanged_redraw_does_not_process_lines(self):
        self.cache.get_spans(self.buffer, 4)
        with patch('femto.highlight.highlight_line') as process:
            for y in (2, 4, 0, 1, 3):
                self.cache.get_spans(self.buffer, y)
            process.assert_not_called()

    def test_new_lines_are_processed_only_as_far_as_requested(self):
        from femto.highlight import highlight_line
        with patch('femto.highlight.highlight_line',
                   wraps=highlight_line) as process:
            self.cache.get_spans(self.buffer, 2)
            self.assertEqual(process.call_count, 3)
            self.cache.get_spans(self.buffer, 1)
            self.assertEqual(process.call_count, 3)
            self.cache.get_spans(self.buffer, 4)
            self.assertEqual(process.call_count, 5)

    def test_insert_and_remove_lines_rebuilds_context(self):
        self.cache.get_spans(self.buffer, 4)
        self.buffer.insert_newline(0, 0)
        self.assertEqual(self.cache.get_spans(self.buffer, 3), [(0, 6, 4)])
        self.buffer.backspace(0, 1)
        self.assertEqual(self.cache.get_spans(self.buffer, 2), [(0, 6, 4)])
        self.buffer.lines.pop(0)
        self.buffer.touch()
        self.assertEqual(self.cache.get_spans(self.buffer, 1), [(0, 6, 5)])

    def test_reload_with_same_revision_and_filename(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'example.py'
            path.write_text('"""\nreturn\n"""\n')
            self.buffer.load_file(str(path))
            self.assertEqual(self.cache.get_spans(self.buffer, 1),
                             [(0, 6, 4)])
            path.write_text('\nreturn\n')
            self.buffer.load_file(str(path))
            self.assertEqual(self.buffer.revision, 0)
            self.assertEqual(self.cache.get_spans(self.buffer, 1),
                             [(0, 6, 5)])


class TestContinuedStringHighlighting(unittest.TestCase):
    def setUp(self):
        from femto import highlight
        self.highlight = highlight
        highlight._CACHE.clear()

    def test_ordinary_quote_state_ends_at_matching_quote(self):
        for quote, apparent in (('"', "'''"), ("'", '"""')):
            for prefix in ('', 'r', 'b', 'u', 'f', 'R', 'br', 'rf'):
                with self.subTest(quote=quote, prefix=prefix):
                    line = 'value = ' + prefix + quote + '\\'
                    spans, state = self.highlight.highlight_line(line)
                    self.assertEqual(spans, [(8 + len(prefix), len(line), 4)])
                    self.assertEqual(state, quote)
                    self.assertEqual(self.highlight.highlight_line(
                        apparent + quote, state), ([(0, 4, 4)], None))
                    self.assertEqual(
                        self.highlight.highlight_line('answer = 42'),
                        ([(9, 11, 6)], None))

    def test_escaped_quotes_and_multiple_continuations(self):
        for quote, apparent in (('"', "'''"), ("'", '"""')):
            with self.subTest(quote=quote):
                lines = ['value = ' + quote + '\\',
                         '\\' + quote + apparent + '\\',
                         quote + '; return_value = 42']
                compile('\n'.join(lines) + '\n', 'escaped.py', 'exec')
                _, state = self.highlight.highlight_line(lines[0])
                self.assertEqual(
                    self.highlight.highlight_line(lines[1], state),
                    ([(0, len(lines[1]), 4)], quote))
                self.assertEqual(
                    self.highlight.highlight_line(lines[2], state),
                    ([(0, 1, 4), (18, 20, 6)], None))

    def test_continuation_requires_odd_trailing_backslashes(self):
        for quote in ('"', "'"):
            for count in range(1, 6):
                with self.subTest(quote=quote, count=count):
                    line = 'value = ' + quote + '\\' * count
                    _, state = self.highlight.highlight_line(line)
                    self.assertEqual(state, quote if count % 2 else None)

    def test_common_string_does_not_continue_over_unescaped_newline(self):
        for quote, apparent in (('"', "'''"), ("'", '"""')):
            with self.subTest(quote=quote):
                # An unfinished edit has no escaped newline on the second line.
                _, state = self.highlight.highlight_line('value = ' + quote
                                                         + '\\')
                spans, state = self.highlight.highlight_line(apparent, state)
                self.assertEqual(spans, [(0, 3, 4)])
                self.assertIsNone(state)
                self.assertEqual(
                    self.highlight.highlight_line('return', state),
                    ([(0, 6, 5)], None))

    def test_closing_common_string_resumes_code_and_triple_strings(self):
        for quote, delimiter in (('"', "'''"), ("'", '"""')):
            with self.subTest(quote=quote):
                line = quote + '; return 42'
                self.assertEqual(self.highlight.highlight_line(line, quote),
                                 ([(0, 1, 4), (3, 9, 5), (10, 12, 6)], None))
                line = quote + ' ' + delimiter
                self.assertEqual(self.highlight.highlight_line(line, quote),
                                 ([(0, 1, 4), (2, 5, 4)], delimiter))

    def test_cache_distinguishes_common_and_triple_quote_contexts(self):
        for quote, delimiter in (('"', "'''"), ("'", '"""')):
            with self.subTest(quote=quote):
                line = delimiter + quote + ' return'
                common = self.highlight.highlight_line(line, quote)
                triple = self.highlight.highlight_line(line, delimiter)
                code = self.highlight.highlight_line(line)
                self.assertEqual(common, ([(0, 4, 4), (5, 11, 5)], None))
                self.assertEqual(triple, ([(0, 3, 4), (5, 11, 5)], None))
                self.assertEqual(code, ([(0, 11, 4)], delimiter))
                for state, result in ((quote, common), (delimiter, triple),
                                      (None, code)):
                    self.assertIs(self.highlight.highlight_line(line, state),
                                  result)


if __name__ == '__main__':
    unittest.main()
