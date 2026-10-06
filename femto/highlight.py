"""
Basic Python syntax highlighter using stdlib regex and keyword modules.
Line results are memoised by text and entering quote state.
Buffer caches carry that state from the start of the document, including
lines above the viewport, and are invalidated by buffer revisions.
"""

import re
import keyword

_TOKEN_RE = re.compile(
    r'(?P<COMMENT>\#.*)|'
    r'(?P<TRIPLE>"""|\'\'\')|'
    r'(?P<STRING>"[^\n"\\]*(?:\\.[^\n"\\]*)*"|'
    r"'[^\n'\\]*(?:\\.[^\n'\\]*)*')|"
    r'(?P<CONTINUED>"[^\n"\\]*(?:\\.[^\n"\\]*)*\\$|'
    r"'[^\n'\\]*(?:\\.[^\n'\\]*)*\\$)|"
    r'(?P<KEYWORD>\b(?:' + '|'.join(keyword.kwlist) + r')\b)|'
    r'(?P<NUMBER>\b\d+(?:\.\d+)?\b)'
)

_COLOR_MAP = {
    'COMMENT': 3,
    'STRING': 4,
    'CONTINUED': 4,
    'KEYWORD': 5,
    'NUMBER': 6,
}

_CACHE = {}
_CACHE_MAX = 4096


def _find_close(line, start, delimiter):
    """Find an unescaped delimiter; backslashes escape one character."""
    pos = start
    while pos < len(line):
        if line[pos] == '\\':
            pos += 2
        elif line.startswith(delimiter, pos):
            return pos
        else:
            pos += 1
    return None


def highlight_line(line, entering_state=None):
    """Return (spans, leaving_state); state is None or a quote delimiter.

    A single quote character represents an ordinary string whose preceding
    line ended with an escaped newline. Triple delimiters span any newline.
    """
    key = (line, entering_state)
    hit = _CACHE.get(key)
    if hit is not None:
        return hit

    spans = []
    state = entering_state
    pos = 0
    if state is not None:
        close = _find_close(line, 0, state)
        pos = len(line) if close is None else close + len(state)
        if pos:
            spans.append((0, pos, _COLOR_MAP['STRING']))
        if close is not None:
            state = None
        elif len(state) == 1:
            # An ordinary string spans another line only with an odd number
            # of trailing backslashes; incomplete edits cannot leak its state.
            if (len(line) - len(line.rstrip('\\'))) % 2 == 0:
                state = None

    while pos < len(line):
        match = _TOKEN_RE.search(line, pos)
        if match is None:
            break
        if match.lastgroup == 'TRIPLE':
            delimiter = match.group()
            close = _find_close(line, match.end(), delimiter)
            pos = len(line) if close is None else close + 3
            spans.append((match.start(), pos, _COLOR_MAP['STRING']))
            if close is None:
                state = delimiter
        else:
            spans.append((match.start(), match.end(),
                          _COLOR_MAP[match.lastgroup]))
            pos = match.end()
            if match.lastgroup == 'CONTINUED':
                state = match.group()[0]

    result = (spans, state)
    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.clear()
    _CACHE[key] = result
    return result


def get_spans(line):
    """Return spans for a standalone line starting outside a string."""
    return highlight_line(line)[0]


class HighlightCache:
    """Lazy line states for one buffer revision, including offscreen lines."""

    def __init__(self):
        self._revision = None
        self._lines = None
        self._results = []

    def get_spans(self, buffer, y):
        # A new line list also invalidates reloads, which reset revision to 0.
        if (self._revision != buffer.revision
                or self._lines is not buffer.lines):
            self._revision = buffer.revision
            self._lines = buffer.lines
            self._results = []

        state = self._results[-1][1] if self._results else None
        while len(self._results) <= y:
            line = buffer.lines[len(self._results)]
            result = highlight_line(line, state)
            self._results.append(result)
            state = result[1]
        return self._results[y][0]
