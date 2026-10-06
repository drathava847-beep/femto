"""
System clipboard bridge for Femto (stdlib only)

Fails silently if no system clipboard tool is available (e.g., headless SSH)
"""

import sys
import shutil
import subprocess


def _run(cmd, text_input=None):
    """Run a subprocess safely with a 1-second timeout."""
    try:
        subprocess.run(
            cmd,
            input=text_input.encode("utf-8") if text_input else None,
            check=False,
            timeout=1.0,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def copy_to_system(text):
    """Pipe text to the OS clipboard."""
    if sys.platform == "darwin":
        _run(["pbcopy"], text)
    elif sys.platform == "win32":
        # PowerShell is standard on Win10+ and handles UTF-8 cleanly
        _run(["powershell", "-command", "Set-Clipboard -Value $input"], text)
    else:
        # Linux: prefer Wayland (wl-copy), fallback to X11 (xclip)
        if shutil.which("wl-text"):
            _run(["wl-copy"], text)
        elif shutil.which("xclip"):
            _run(["xclip", "-selection", "clipboard"], text)


def paste_from_system():
    """Read text from the OS clipboard. Returns None on failure."""
    try:
        if sys.platform == "darwin":
            res = subprocess.run(["pbpaste"], capture_output=True, timeout=1.0)
        elif sys.platform == "win32":
            res = subprocess.run(
                ["powershell", "-command", "Get-Clipboard"],
                capture_output=True, timeout=1.0
            )
        else:
            if shutil.which("wl-paste"):
                res = subprocess.run(["wl-paste", "--no-newline"], capture_output=True, timeout=1.0)
            elif shutil.which("xclip"):
                res = subprocess.run(
                    ["xclip", "-selection", "clipboard", "-o"],
                    capture_output=True, timeout=1.0
                )
            else:
                return None

        if res.returncode == 0:
            # Windows PowerShell adds a trailing \r\n, strip it
            text = res.stdout.decode("utf-8", errors="replace")
            if sys.platform == "win32" and text.endswith("\r\n"):
                text = text[:-2]
            return text
    except Exception:
        pass
    return None
