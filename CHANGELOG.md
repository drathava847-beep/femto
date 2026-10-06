# Changelog

All notable changes to Femto are documented in this file.

## [0.0.3a03]

### Added

- **Word-Boundary Wrapping:** Soft wrap now breaks at spaces instead of mid-word (fixes #19)
- Falls back to hard-cut when a single word exceeds viewport width
- Added `wrap_at_word` config flag (default: `true`)
- Visual/logical coordinate mapping automatically adapts to new chunking
- Added `auto_indent` config option (default: `true`).
- Full-screen categorized F1 help screen with scrolling (fixes #20) - thanks @feliperm17!
- AST-based test
- **I/O Fidelity:** Preserve CRLF/CR/LF line on save; added `line_ending` config (Thanks @HarshRajSinghania!)
- **POSIX Compliance:** Ensure trailing newline on save (fixes #12)
- Added `line_ending` and `final_newline` config options
- Internal buffer normalizes to `\n` to keep cursor math and wrapping clean

### Fixed
- Python syntax highlighting for multi-line strings and docstrings (fixes #14) - thanks @feliperm17!
- Highlighter now carries lexical state across lines.
- Lazy invalidation via `buffer.revision` keeps performance optimal.
- Unicode combining characters (accents, diacritics) now correctly measure as 0 terminal columns (fixes #25) - thanks @drathava847-beep!
- **Smart Auto-Indent:** Enter key copies leading whitespace (fixes #17).
- **Python Awareness:** Automatically adds an extra indent level when the previous line ends with a colon (`:`), correctly ignoring inline `#` comments.
- ZWJ emoji sequences and variation selection now measure correctly in soft wrap (fixes #16) - thanks @drathava847-beep!

### Tests
- All search matches highlighted on screen with revision-keyed caching (fixes #22) - thanks @drathava847-beep!
- Added regression test for hard-wrap behavior in `get_visual_postion()` with mutation validation (thanks @drathava847-beep!).

## [0.0.2] - Stable

- **Multi-buffer editing:** Open multiple files (`femto a b c`), switch with `Ctrl+F` / `Ctrl+L`.
- **Selection & Clipboard:** `Ctrl+B` (mark), `Ctrl+K` (cut), `Ctrl+P` (copy), `Ctrl+U` (paste).
- **Search & Replace:** `Ctrl+\` flow with per-match `Y/N/A/C` confirm. Regex and case-insensitive toggles (`Ctrl+R`, `Ctrl+O`).
- **Readability:** Dynamic line-number gutter (`Ctrl+N`), pure-Python syntax highlighting for `.py` files.
- **Mouse Support:** Wheel scrolling and click-to-cursor (`Ctrl+D` toggle).
- **Unicode Fidelity:** Width-aware layout math for CJK and Emoji characters (no more broken soft-wrap).
- **Platform Hardening:** Windows `Shift+Tab` / `Ctrl+Arrow` fallbacks, robust Alt/Ctrl key decoding.
- **Performance & Safety:** Atomic saves (`fsync` + `os.replace`), optional `name~` backups, frame-signature redraw skip, memoised syntax highlighting.

## [0.0.1] - Stable
- Packaging: `pyproject.toml`, console script `femto`, `python -m femto`
- CLI flags: `--version`, `--tab-size`, `--scroll-margin`, `--no-wrap`
- New `layout.py` (curses-free visual mapping) + unittest regression suite
- `soft_wrap = false` now works (horizontal-scroll fallback)
- Page Up/Down respect soft-wrapped visual rows
- Scroll clamping for very small terminals; ASCII-safe status messages
- MIT license, finalized README
- Visual soft line wrapping, smooth scrolling, `.femtorc` config parsing
- Search (Ctrl+W), Go-To-Line (Ctrl+T), snapshot Undo/Redo (Ctrl+Z / Ctrl+Y)
- Mode state machine, Save-As prompt, exit confirmation (Y/N/C)
- Word jump, Page Up/Down, Home/End, Tab / Shift-Tab indentation
- Initial alpha: load/save, arrows, insert/delete, nano-style status bar