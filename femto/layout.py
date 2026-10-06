"""
Layout and soft-wrap logic for Femto.

Width model (stdlib only):
  * combining marks (category M*) and U+FE0F (VS16) occupy 0 columns
  * U+200D (ZWJ) occupies 0 columns AND joins the next character into
    the previous cluster, which then also occupies 0 columns (PR #24)
  * East Asian Wide/Fullwidth occupy 2 columns (PR #8)
  * everything else occupies 1 column

Wrapping (v0.0.3a03):
  * chunk_line() breaks at the last space within the width
  * hard-cut fallback when a single word exceeds the width
"""

import unicodedata


def char_width(ch):
    """Context-free display width of a single character."""
    if unicodedata.category(ch).startswith('M'):
        return 0
    if ch in ('\u200D', '\uFE0F'):
        return 0
    return 2 if unicodedata.east_asian_width(ch) in ('W', 'F') else 1


def _widths(line):
    """Per-character display widths with ZWJ cluster joining."""
    widths = []
    joined = False
    for ch in line:
        if ch == '\u200D':
            widths.append(0)
            joined = True
            continue
        if joined:
            widths.append(0)
            joined = False
            continue
        widths.append(char_width(ch))
    return widths


def str_width(s):
    """Display width of a string in terminal columns."""
    return sum(_widths(s))


def chunk_line(line, width):
    """Split a line into chunks of at most `width` display columns.

    Word-boundary wrapping: breaks at the last space within the width.
    Falls back to hard-cut when a single word exceeds width.
    """
    if not line:
        return [""]
    if width <= 0:
        return [line]

    ws = _widths(line)
    chunks = []
    pos = 0
    n = len(line)

    while pos < n:
        col = 0
        end = pos
        last_space = -1
        while end < n and col < width:
            w = ws[end]
            if col + w > width:
                break
            col += w
            if line[end] == ' ':
                last_space = end
            end += 1

        if end == n:
            chunks.append(line[pos:])
            break
        if last_space > pos:
            chunks.append(line[pos:last_space + 1])
            pos = last_space + 1
        else:
            chunks.append(line[pos:end])
            pos = end

    return chunks


def line_row_count(line_len, width):
    """Approximate row count for hard-wrap mode."""
    if line_len == 0 or width <= 0:
        return 1
    return max(1, (line_len + width - 1) // width)


def get_visual_position(x, y, lines, width, soft_wrap=True):
    """Convert logical (x, y) to visual (col, row) coordinates."""
    if not soft_wrap:
        return x, y
    if not (0 <= y < len(lines)):
        return 0, 0

    line = lines[y]
    rows_before = 0
    for i in range(y):
        rows_before += len(chunk_line(lines[i], width))

    chunks = chunk_line(line, width)
    x = max(0, min(x, len(line)))

    start = 0
    for i, chunk in enumerate(chunks):
        end = start + len(chunk)
        if x < end:
            return str_width(line[start:x]), rows_before + i
        if x == end and i == len(chunks) - 1:
            # Cursor at end of line: wrap to next row only if this
            # row is exactly full; otherwise sit at the row's edge.
            if chunk and str_width(chunk) == width:
                return 0, rows_before + i + 1
            return str_width(chunk), rows_before + i
        start = end
    return 0, rows_before


def get_logical_from_visual(vy, lines, width, soft_wrap=True):
    """Convert visual row to logical line index."""
    if not soft_wrap:
        return vy
    row = 0
    for y, line in enumerate(lines):
        rows = len(chunk_line(line, width))
        if row + rows > vy:
            return y
        row += rows
    return max(0, len(lines) - 1)


def col_to_index(line, display_col):
    """Convert a display-column offset into a character index in `line`.

    A display column that falls inside a wide character maps to the
    start of that character; zero-width chars are skipped.
    """
    ws = _widths(line)
    col = 0
    for i, w in enumerate(ws):
        if display_col < col + w:
            return i
        col += w
    return len(line)


def get_logical_from_visual_point(target_vy, target_vx, lines, width,
                                  soft_wrap=True):
    """Map a visual (row, display-column) point to logical (x, y).

    Used by mouse click-to-cursor.  In hard-wrap mode the mapping is
    the identity (the caller has already added scroll offsets).
    """
    if not soft_wrap:
        return target_vx, target_vy

    vy = 0
    for y, line in enumerate(lines):
        chunks = chunk_line(line, width)
        rows = len(chunks)
        if vy + rows > target_vy:
            i = target_vy - vy
            offset = sum(str_width(c) for c in chunks[:i])
            return col_to_index(line, offset + target_vx), y
        vy += rows
    y = max(0, len(lines) - 1)
    return len(lines[y]), y
