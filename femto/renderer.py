"""
Terminal rendering engine for Femto using curses.

Integrates: soft wrap (word-boundary or hard-cut), hard wrap, line-number
gutter, syntax highlighting, four-level overlays
(syntax < all-matches < active match < selection), F1 help screen,
frame-signature redraw skip, and chunk memoisation.
"""

import curses
from weakref import WeakKeyDictionary
from femto import __version__, __app_name__
from femto.layout import chunk_line, get_visual_position
from femto.highlight import HighlightCache

BAR_STYLE = "color"


class Renderer:
    def __init__(self, stdscr, config):
        self.stdscr = stdscr
        self.config = config
        self.bar_attr = curses.A_REVERSE
        self.prompt_attr = curses.A_REVERSE | curses.A_BOLD
        self.sel_attr = curses.A_REVERSE
        self.match_attr = curses.A_REVERSE | curses.A_BOLD
        self.all_match_attr = curses.A_UNDERLINE
        self.gutter_attr = curses.A_BOLD
        self._last_sig = None
        self._chunk_cache = {}
        self._hard_cache = {}
        self._highlight_caches = WeakKeyDictionary()
        self.setup_colors()

    def _load_keybindings():
        """Locate the KEYBINDINGS catalog without a hard import."""
        for modname in ("femto.help", "femto.keys", "femto.app"):
            try:
                mod = __import__(modname, fromlist=["KEYBINDINGS"])
            except Exception:
                continue
            cat = getattr(mod, "KEYBINDINGS", None)
            if cat:
                return cat
        return {"General": [("^X", "Exit"), ("^S", "Save"), ("F1", "Help")]}

    def setup_colors(self):
        if BAR_STYLE != "color":
            return
        try:
            curses.start_color()
            try:
                curses.use_default_colors()
                bg = -1
            except curses.error:
                bg = curses.COLOR_BLACK

            curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)
            curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_YELLOW)
            curses.init_pair(3, curses.COLOR_GREEN, bg)
            curses.init_pair(4, curses.COLOR_MAGENTA, bg)
            curses.init_pair(5, curses.COLOR_CYAN, bg)
            curses.init_pair(6, curses.COLOR_YELLOW, bg)
            curses.init_pair(7, curses.COLOR_BLUE, bg)

            self.bar_attr = curses.color_pair(1)
            self.prompt_attr = curses.color_pair(2) | curses.A_BOLD
            self.match_attr = curses.color_pair(2)
            self.gutter_attr = curses.color_pair(7) | curses.A_BOLD
        except curses.error:
            pass

    def get_dimensions(self):
        height, width = self.stdscr.getmaxyx()
        return max(1, height - 2), max(1, width)

    # ── safe primitives ───────────────────────────────────────

    def _safe_addstr(self, row, col, text, attr=0):
        try:
            if attr:
                self.stdscr.addstr(row, col, text, attr)
            else:
                self.stdscr.addstr(row, col, text)
        except curses.error:
            pass

    def _safe_move(self, row, col):
        try:
            self.stdscr.move(row, col)
        except curses.error:
            pass

    # ── chunk caches ──────────────────────────────────────────

    def _chunks_for(self, line, width):
        """Word-boundary chunks (memoised)."""
        key = (line, width)
        chunks = self._chunk_cache.get(key)
        if chunks is None:
            chunks = chunk_line(line, width)
            if len(self._chunk_cache) > 2048:
                self._chunk_cache.clear()
            self._chunk_cache[key] = chunks
        return chunks

    def _hard_chunks_for(self, line, width):
        """Mid-word hard-cut chunks (memoised), for wrap_at_word=false."""
        key = (line, width)
        chunks = self._hard_cache.get(key)
        if chunks is None:
            chunks = [line[i:i + width] for i in range(0, len(line), width)]
            if not chunks:
                chunks = [""]
            if len(self._hard_cache) > 2048:
                self._hard_cache.clear()
            self._hard_cache[key] = chunks
        return chunks

    def _chunks(self, line, width):
        if getattr(self.config, 'wrap_at_word', True):
            return self._chunks_for(line, width)
        return self._hard_chunks_for(line, width)

    def _highlights_for(self, buffer, y):
        if (not self.config.syntax_highlight or not buffer.filename
                or not buffer.filename.endswith('.py')):
            return []
        cache = self._highlight_caches.get(buffer)
        if cache is None:
            cache = HighlightCache()
            self._highlight_caches[buffer] = cache
        return cache.get_spans(buffer, y)

    # ── Text area ─────────────────────────────────────────────

    def draw_text(self, buffer, cursor, screen_rows, screen_cols,
                  sel=None, match=None, all_matches=None):
        gutter_width = (len(str(len(buffer.lines))) + 1
                        if self.config.show_line_numbers else 0)
        text_cols = max(1, screen_cols - gutter_width)

        if not self.config.soft_wrap:
            self._draw_text_hard(buffer, cursor, screen_rows, text_cols,
                                 sel, match, all_matches, gutter_width)
            return

        visual_row = 0
        for y, line in enumerate(buffer.lines):
            chunks = self._chunks(line, text_cols)

            for i, chunk in enumerate(chunks):
                if visual_row < cursor.scroll_y:
                    visual_row += 1
                    continue
                if visual_row >= cursor.scroll_y + screen_rows:
                    return

                draw_y = visual_row - cursor.scroll_y

                if self.config.show_line_numbers:
                    self._safe_move(draw_y, 0)
                    if i == 0:
                        num_str = str(y + 1).rjust(gutter_width - 1) + " "
                        self._safe_addstr(draw_y, 0, num_str, self.gutter_attr)
                    else:
                        self._safe_addstr(draw_y, 0, " " * gutter_width)

                self._safe_move(draw_y, gutter_width)
                try:
                    self.stdscr.clrtoeol()
                except curses.error:
                    pass

                highlights = self._highlights_for(buffer, y)

                logical_x0 = sum(len(c) for c in chunks[:i])
                self._draw_chunk(draw_y, chunk, logical_x0, y,
                                 sel, match, all_matches,
                                 highlights, gutter_width)
                visual_row += 1

        while visual_row - cursor.scroll_y < screen_rows:
            draw_y = visual_row - cursor.scroll_y
            if draw_y >= 0:
                self._safe_move(draw_y, 0)
                try:
                    self.stdscr.clrtoeol()
                except curses.error:
                    pass
                if self.config.show_line_numbers:
                    self._safe_addstr(draw_y, 0, " " * gutter_width)
                self._safe_addstr(draw_y, gutter_width, "~", curses.A_BOLD)
            visual_row += 1

    def _draw_text_hard(self, buffer, cursor, screen_rows, text_cols,
                        sel, match, all_matches, gutter_width):
        for row in range(screen_rows):
            y = row + cursor.scroll_y
            self._safe_move(row, 0)
            try:
                self.stdscr.clrtoeol()
            except curses.error:
                pass

            if self.config.show_line_numbers:
                if y < len(buffer.lines):
                    num_str = str(y + 1).rjust(gutter_width - 1) + " "
                    self._safe_addstr(row, 0, num_str, self.gutter_attr)
                else:
                    self._safe_addstr(row, 0, " " * gutter_width)

            if y < len(buffer.lines):
                x0 = cursor.scroll_x
                chunk = buffer.lines[y][x0:x0 + text_cols]

                highlights = self._highlights_for(buffer, y)

                self._draw_chunk(row, chunk, x0, y, sel, match,
                                 all_matches, highlights, gutter_width)
            else:
                self._safe_addstr(row, gutter_width, "~", curses.A_BOLD)

    # ── highlight & overlay machinery ─────────────────────────

    def _overlap(self, bounds, x0, y, chunk_len):
        (sx, sy), (ex, ey) = bounds
        if not (sy <= y <= ey):
            return None
        line_start = sx if y == sy else 0
        line_end = ex if y == ey else x0 + chunk_len
        lo = max(0, line_start - x0)
        hi = min(chunk_len, line_end - x0)
        return (lo, hi) if lo < hi else None

    def _draw_chunk(self, row, chunk, x0, y, sel, match, all_matches,
                    highlights, gutter_offset=0):
        if not chunk:
            return

        intervals = []

        # Priority 1 (lowest): syntax highlights
        for hs, he, color_id in highlights:
            lo = max(0, hs - x0)
            hi = min(len(chunk), he - x0)
            if lo < hi:
                intervals.append((lo, hi, curses.color_pair(color_id)))

        # Priority 2: all search matches (background underline)
        if all_matches:
            for mx, my, ml in all_matches:
                if my == y:
                    lo = max(0, mx - x0)
                    hi = min(len(chunk), mx + ml - x0)
                    if lo < hi:
                        intervals.append((lo, hi, self.all_match_attr))

        # Priority 3: active match
        if match is not None:
            mx, my, ml = match
            if my == y:
                lo = max(0, mx - x0)
                hi = min(len(chunk), mx + ml - x0)
                if lo < hi:
                    intervals.append((lo, hi, self.match_attr))

        # Priority 4 (highest): selection
        if sel is not None:
            iv = self._overlap(sel, x0, y, len(chunk))
            if iv:
                intervals.append((iv[0], iv[1], self.sel_attr))

        self._safe_addstr(row, gutter_offset, chunk)
        for lo, hi, attr in intervals:
            self._safe_addstr(row, gutter_offset + lo, chunk[lo:hi], attr)

    # ── Bottom bars ───────────────────────────────────────────

    def draw_status_bar(self, buffer, cursor, screen_rows, screen_cols,
                        message="", mark_set=False,
                        doc_index=0, doc_count=1):
        status = f" {__app_name__} v{__version__}"
        status += f"  {buffer.filename or 'New Buffer'}"
        if doc_count > 1:
            status += f"  [{doc_index + 1}/{doc_count}]"
        if buffer.modified:
            status += "  [Modified]"
        if mark_set:
            status += "  [Mark]"
        if self.config.mouse:
            status += "  [Mouse]"
        status += f"  Ln {cursor.y + 1}, Col {cursor.x + 1}"
        if message:
            status += f"  | {message}"

        self._draw_bar(screen_rows, status, screen_cols, self.bar_attr)
        self._draw_bar(
            screen_rows + 1,
            "^X Exit  ^S Save  ^W Find  ^K Cut  ^U Paste  ^F/^L Buf  F1 Help",
            screen_cols, self.bar_attr,
        )

    def draw_prompt(self, prompt, screen_rows, screen_cols, help_text=""):
        self._draw_bar(screen_rows, prompt.get_display(screen_cols),
                       screen_cols, self.prompt_attr)
        self._draw_bar(screen_rows + 1, help_text, screen_cols, self.bar_attr)
        cx = min(prompt.get_cursor_x(), screen_cols - 1)
        self._safe_move(screen_rows, cx)

    def _draw_confirm(self, display, help_text, screen_rows, screen_cols):
        self._draw_bar(screen_rows, display, screen_cols, self.prompt_attr)
        self._draw_bar(screen_rows + 1, help_text, screen_cols, self.bar_attr)

    def draw_exit_confirm(self, message, screen_rows, screen_cols):
        self._draw_confirm(
            f" {message}  (Y)es / (N)o / (C)ancel",
            "Y Yes    N No    C Cancel", screen_rows, screen_cols)

    def draw_replace_confirm(self, message, screen_rows, screen_cols):
        self._draw_confirm(
            f" {message}  (Y)es / (N)o / (A)ll / (C)ancel",
            "Y Yes    N No    A All    C Cancel", screen_rows, screen_cols)

    # ── F1 help screen ────────────────────────────────────────

    def draw_help_screen(self, screen_rows, screen_cols, help_scroll_y,
                         keybindings):
        """Full-screen categorized help view; Esc/q return to editing."""
        try:
            self.stdscr.erase()
        except curses.error:
            pass

        header = f" {__app_name__} Help - Esc or q returns "
        self._draw_bar(0, header, screen_cols, self.bar_attr)

        if not keybindings:
            keybindings = _load_keybindings()

        # Flatten catalog into (text, attr) content lines
        content = []
        for category, bindings in (keybindings or {}).items():
            content.append((f"-- {category} --", curses.A_BOLD))
            for item in bindings:
                if isinstance(item, (tuple, list)) and len(item) == 2:
                    key, desc = item
                    content.append((f"   {key:<22} {desc}", 0))
                else:
                    content.append((f"   {item}", 0))
            content.append(("", 0))

        last = max(0, screen_rows - 2)
        for idx, (text, attr) in enumerate(content):
            vis = idx - help_scroll_y
            if vis < 0:
                continue
            if vis > last:
                break
            self._safe_addstr(1 + vis, 0, text[:screen_cols], attr)

        more = "  ..." if help_scroll_y + (last + 1) < len(content) else ""
        hint = f" Up/Down scroll   PgUp/PgDn page   Esc/q exit{more}"
        self._draw_bar(screen_rows - 1, hint, screen_cols, self.bar_attr)

        try:
            self.stdscr.refresh()
        except curses.error:
            pass

    def _draw_bar(self, row, text, width, attr):
        text = text.ljust(width)[:width]
        try:
            self.stdscr.addstr(row, 0, text, attr)
        except curses.error:
            pass

    def draw_cursor(self, cursor, buffer, screen_cols):
        gutter_width = (len(str(len(buffer.lines))) + 1
                        if self.config.show_line_numbers else 0)
        text_cols = max(1, screen_cols - gutter_width)
        vx, vy = get_visual_position(
            cursor.x, cursor.y, buffer.lines, text_cols,
            self.config.soft_wrap)
        try:
            self.stdscr.move(vy - cursor.scroll_y,
                             vx - cursor.scroll_x + gutter_width)
        except curses.error:
            pass

    _PROMPT_HELP = {
        "save_as": "Enter Save    Tab Complete    ^G Cancel",
        "search": "Enter Find Next    ^O Case    ^R Regex    ^G Cancel",
        "replace_search": "Enter Continue    ^O Case    ^R Regex    ^G Cancel",
        "replace_with": "Enter Confirm    ^G Cancel",
        "goto_line": "Enter Jump    ^G Cancel",
    }

    # ── Main entry ────────────────────────────────────────────

    def render(self, buffer, cursor, message="", prompt=None, mode="normal",
               selection=None, mark_set=False, match=None,
               all_matches=None, keybindings=None,
               doc_index=0, doc_count=1, help_scroll_y=0):
        screen_rows, screen_cols = self.get_dimensions()

        # F1 help screen uses a dedicated render path
        if mode == "help":
            self.draw_help_screen(screen_rows, screen_cols,
                                  help_scroll_y, keybindings)
            return

        # ── frame signature: skip completely unchanged frames ──
        sig = (
            buffer, buffer.filename, id(buffer.lines),
            getattr(buffer, "revision", 0),
            cursor.x, cursor.y, cursor.scroll_x, cursor.scroll_y,
            selection, match, message, mode, mark_set,
            screen_rows, screen_cols, doc_index, doc_count,
            self.config.show_line_numbers, self.config.mouse,
            (len(all_matches), all_matches[0] if all_matches else None)
            if all_matches else None,
            self.config.syntax_highlight, self.config.soft_wrap,
            getattr(self.config, "wrap_at_word", True),
            (prompt.label, prompt.text, prompt.cursor_pos)
            if prompt and prompt.active else None,
        )
        if sig == self._last_sig:
            return
        self._last_sig = sig

        try:
            self.stdscr.erase()
        except curses.error:
            pass

        self.draw_text(buffer, cursor, screen_rows, screen_cols,
                       selection, match, all_matches)

        if prompt and prompt.active and mode in self._PROMPT_HELP:
            self.draw_prompt(prompt, screen_rows, screen_cols,
                             self._PROMPT_HELP[mode])
        elif mode == "exit_confirm":
            self.draw_exit_confirm(message, screen_rows, screen_cols)
            self.draw_cursor(cursor, buffer, screen_cols)
        elif mode == "replace_confirm":
            self.draw_replace_confirm(message, screen_rows, screen_cols)
            self.draw_cursor(cursor, buffer, screen_cols)
        else:
            self.draw_status_bar(buffer, cursor, screen_rows, screen_cols,
                                 message, mark_set, doc_index, doc_count)
            self.draw_cursor(cursor, buffer, screen_cols)

        try:
            self.stdscr.refresh()
        except curses.error:
            pass
