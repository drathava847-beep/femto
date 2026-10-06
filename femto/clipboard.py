"""
Clipboard and anchor-based selection (mark) support for Femto.

Selection semantics:
  * The mark is an anchor point; the selection is the range between
    the anchor and the live cursor (normalized on read).
  * Bounds are half-open: [start, end).
  * Anchors are clamped against the buffer on every read so undo/redo
    or deletes can never produce out-of-range selections.
"""


class Selection:
    """Anchor-based text selection state."""

    def __init__(self):
        self.active = False
        self.anchor_x = 0
        self.anchor_y = 0

    def toggle(self, x, y):
        """Set the mark at (x, y); returns True if the mark is now on."""
        if self.active:
            self.clear()
            return False
        self.active = True
        self.anchor_x = x
        self.anchor_y = y
        return True

    def clear(self):
        self.active = False

    def clamped_anchor(self, buffer):
        ay = max(0, min(self.anchor_y, buffer.max_y))
        ax = max(0, min(self.anchor_x, buffer.get_line_length(ay)))
        return ax, ay

    def bounds(self, buffer, cx, cy):
        """Normalized ((start_x, start_y), (end_x, end_y)) for cursor (cx, cy)."""
        ax, ay = self.clamped_anchor(buffer)
        if (ay, ax) <= (cy, cx):
            return (ax, ay), (cx, cy)
        return (cx, cy), (ax, ay)

    def is_empty(self, bounds):
        return bounds[0] == bounds[1]

    def extract(self, buffer, bounds):
        """Return the selected text."""
        (sx, sy), (ex, ey) = bounds
        if sy == ey:
            return buffer.lines[sy][sx:ex]
        parts = [buffer.lines[sy][sx:]]
        parts.extend(buffer.lines[y] for y in range(sy + 1, ey))
        parts.append(buffer.lines[ey][:ex])
        return "\n".join(parts)

    def delete_range(self, buffer, bounds):
        """Remove [start, end) from the buffer; returns new cursor (x, y)."""
        (sx, sy), (ex, ey) = bounds
        if sy == ey:
            line = buffer.lines[sy]
            buffer.lines[sy] = line[:sx] + line[ex:]
        else:
            merged = buffer.lines[sy][:sx] + buffer.lines[ey][ex:]
            del buffer.lines[sy:ey + 1]
            buffer.lines.insert(sy, merged)
        buffer.touch()
        return sx, sy


class Clipboard:
    """Simple in-memory text clipboard."""

    def __init__(self):
        self.text = ""

    @property
    def empty(self):
        return not self.text

    def store(self, text):
        self.text = text

    def paste_into(self, buffer, x, y):
        """Insert clipboard text at (x, y); returns new cursor (x, y)."""
        if not self.text:
            return x, y
        chunks = self.text.split("\n")
        line = buffer.lines[y]
        head, tail = line[:x], line[x:]
        if len(chunks) == 1:
            buffer.lines[y] = head + chunks[0] + tail
            new_pos = (x + len(chunks[0]), y)
        else:
            first = head + chunks[0]
            last = chunks[-1] + tail
            buffer.lines[y:y + 1] = [first] + chunks[1:-1] + [last]
            new_pos = (len(chunks[-1]), y + len(chunks) - 1)
        buffer.touch()
        return new_pos
