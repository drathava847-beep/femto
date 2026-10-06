"""
Search engine for Femto: plain, case-insensitive and regex matching.

Matching is line-based: a match never spans multiple lines, which keeps
visual highlighting and replacement math simple and predictable.
"""

import re


class SearchOptions:
    """Runtime search flags (toggleable from the search prompt)."""

    def __init__(self, ignore_case=False, regex=False):
        self.ignore_case = ignore_case
        self.regex = regex

    def flag_label(self):
        tags = ""
        if self.ignore_case:
            tags += "i"
        if self.regex:
            tags += "r"
        return f" [{tags}]" if tags else ""


def find_in_line(line, term, options, start=0):
    """First match in `line` at/after `start`; returns (pos, end) or None."""
    if not term:
        return None
    if options.regex:
        flags = re.IGNORECASE if options.ignore_case else 0
        try:
            rx = re.compile(term, flags)
        except re.error:
            return None
        m = rx.search(line, start)
        return (m.start(), m.end()) if m else None
    if options.ignore_case:
        pos = line.lower().find(term.lower(), start)
    else:
        pos = line.find(term, start)
    return (pos, pos + len(term)) if pos != -1 else None


def find_next(buffer, term, options, start_x, start_y, wrap=True):
    """
    Forward search from (start_x, start_y).

    Returns (x, y, length) of the match, or None.
    With wrap=False the search stops at the end of the buffer
    (used by the replace flow to guarantee termination).
    """
    n = len(buffer.lines)
    if n == 0 or not term:
        return None
    steps = n if wrap else n - start_y
    for i in range(steps):
        y = (start_y + i) % n if wrap else start_y + i
        start = start_x if i == 0 else 0
        hit = find_in_line(buffer.lines[y], term, options, start)
        if hit:
            pos, end = hit
            return pos, y, end - pos
    return None

def find_all(buffer, term, options):
    """Return all matches in the buffer as (pos, y, length)."""
    matches = []
    for y, line in enumerate(buffer.lines):
        start = 0
        while True:
            hit = find_in_line(line, term, options, start)
            if hit is None:
                break
            pos, end = hit
            matches.append((pos, y, end - pos))
            start = end if end > pos else pos + 1
    return matches


def replace_in_line(line, pos, end, replacement):
    """Splice `replacement` over [pos, end) in `line`."""
    return line[:pos] + replacement + line[end:]
