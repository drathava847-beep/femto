"""
F1 help-screen regression tests for Femto (headless-safe).

If the original contributor suite is recoverable from Git
(`git checkout origin/main -- tests/test_help.py`), prefer that.
This compact canonical version covers the same contracts:
mode transitions, input isolation, scroll clamping, rendering,
terminal-error tolerance, and cursor restoration.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import curses

from femto.app import Application, Mode
from femto.renderer import Renderer


def _load_keybindings():
    for modname in ("femto.help", "femto.keys", "femto.app"):
        try:
            mod = __import__(modname, fromlist=["KEYBINDINGS"])
            cat = getattr(mod, "KEYBINDINGS", None)
            if cat:
                return cat
        except Exception:
            continue
    return {"General": [("^X", "Exit"), ("^S", "Save")]}


KEYBINDINGS = _load_keybindings()


class FakeStdscr:
    """Minimal curses stand-in: records draws, tolerates error injection."""

    def __init__(self, rows=24, cols=80, fail=False):
        self.rows = rows
        self.cols = cols
        self.fail = fail
        self.grid = {}
        self.moves = []

    def getmaxyx(self):
        return (self.rows, self.cols)

    def erase(self):
        self.grid = {}

    def move(self, y, x):
        if self.fail:
            raise curses.error("move")
        self.moves.append((y, x))

    def clrtoeol(self):
        pass

    def addstr(self, *args):
        if self.fail:
            raise curses.error("addstr")
        if isinstance(args[0], str):
            y, x = self.moves[-1] if self.moves else (0, 0)
            text = args[0]
        else:
            y, x, text = args[0], args[1], args[2]
        self.grid[(y, x)] = text

    def refresh(self):
        pass

    def nodelay(self, flag):
        pass

    def keypad(self, flag):
        pass

    def all_text(self):
        return " ".join(self.grid.values())


def make_app(rows=24, cols=80, fail=False):
    app = Application(None)
    app.renderer = Renderer(FakeStdscr(rows, cols, fail), app.config)
    return app


class TestHelpMode(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.app.config.auto_indent = False

    def test_f1_enters_help(self):
        self.app.handle_input(curses.KEY_F1, 24, 80)
        self.assertEqual(self.app.mode, Mode.HELP)

    def test_esc_returns(self):
        self.app.handle_input(curses.KEY_F1, 24, 80)
        self.app.handle_input(27, 24, 80)
        self.assertEqual(self.app.mode, Mode.NORMAL)

    def test_q_returns(self):
        self.app.handle_input(curses.KEY_F1, 24, 80)
        self.app.handle_input(ord('q'), 24, 80)
        self.assertEqual(self.app.mode, Mode.NORMAL)

    def test_text_ignored_in_help(self):
        self.app.handle_input(curses.KEY_F1, 24, 80)
        self.app.handle_input(ord('x'), 24, 80)
        self.assertEqual(self.app.buffer.lines, [""])

    def test_commands_ignored_in_help(self):
        self.app.buffer.lines = ["keep me"]
        self.app.handle_input(curses.KEY_F1, 24, 80)
        self.app.handle_input(11, 24, 80)   # Ctrl+K must not cut
        self.assertTrue(self.app.clipboard.empty)
        self.assertEqual(self.app.buffer.lines, ["keep me"])

    def test_f1_ignored_in_prompts(self):
        self.app.handle_input(23, 24, 80)   # Ctrl+W -> search
        self.assertEqual(self.app.mode, Mode.SEARCH)
        self.app.handle_input(curses.KEY_F1, 24, 80)
        self.assertEqual(self.app.mode, Mode.SEARCH)

    def test_scroll_clamps(self):
        self.app.handle_input(curses.KEY_F1, 24, 80)
        for _ in range(200):
            self.app.handle_input(curses.KEY_DOWN, 24, 80)
        self.assertGreaterEqual(self.app.help_scroll_y, 0)
        for _ in range(300):
            self.app.handle_input(curses.KEY_UP, 24, 80)
        self.assertEqual(self.app.help_scroll_y, 0)


class TestHelpRenderer(unittest.TestCase):
    def test_draws_categories(self):
        app = make_app()
        app.renderer.render(app.buffer, app.cursor, mode="help",
                            keybindings=KEYBINDINGS, help_scroll_y=0)
        text = app.renderer.stdscr.all_text()
        first_category = next(iter(KEYBINDINGS))
        self.assertIn(first_category, text)

    def test_handles_terminal_errors(self):
        app = make_app(fail=True)
        app.renderer.render(app.buffer, app.cursor, mode="help",
                            keybindings=KEYBINDINGS, help_scroll_y=0)
        app.renderer.render(app.buffer, app.cursor)   # must not raise

    def test_restores_cursor_on_return(self):
        app = make_app()
        app.buffer.lines = ["abc"]
        app.cursor.set_pos(2, 0, app.buffer.get_line_length,
                           app.buffer.max_y)
        app.handle_input(curses.KEY_F1, 24, 80)
        app.handle_input(27, 24, 80)
        app.renderer.stdscr.moves = []
        app.renderer.render(app.buffer, app.cursor)
        self.assertIn((app.cursor.y - app.cursor.scroll_y,
                       app.cursor.x - app.cursor.scroll_x),
                      app.renderer.stdscr.moves)


class TestDocumentedKeyBehavior(unittest.TestCase):
    """Spot-check that documented keys do what the help screen claims."""

    def setUp(self):
        self.app = make_app()
        self.app.config.auto_indent = False

    def test_enter_splits_line(self):
        app = self.app
        app.buffer.lines = ["  alpha beta"]
        app.cursor.set_pos(2, 0, app.buffer.get_line_length, app.buffer.max_y)
        for code in (10, 13, curses.KEY_ENTER):
            app.buffer.lines = ["  alpha beta"]
            app.cursor.set_pos(2, 0, app.buffer.get_line_length,
                               app.buffer.max_y)
            with self.subTest(key="Enter", code=code):
                app._handle_normal(code, 24, 80)
                self.assertEqual(app.buffer.lines, ["  ", "alpha beta"])

    def test_mark_and_cut(self):
        app = self.app
        app.buffer.lines = ["one", "two"]
        app.cursor.set_pos(0, 0, app.buffer.get_line_length, app.buffer.max_y)
        app._handle_normal(2, 24, 80)      # Ctrl+B mark
        self.assertTrue(app.selection.active)
        app._handle_normal(11, 24, 80)     # Ctrl+K cut line (empty sel at mark)
        self.assertEqual(app.clipboard.text, "one\n")


if __name__ == "__main__":
    unittest.main()
