"""
Configuration file parser for Femto.
Looks for ~/.femtorc or ./.femtorc
"""

import os


class Config:
    def __init__(self):
        self.tab_size = 4
        self.smooth_scroll_margin = 3
        self.soft_wrap = True
        self.ignore_case = False      
        self.regex_search = False 
        self.show_line_numbers = False   
        self.syntax_highlight = True
        self.mouse = False    
        self.make_backup = False
        self.line_ending = 'auto'
        self.final_newline = True
        self.auto_indent = True
        self.wrap_at_word = True
        self.system_clipboard = False
        self.load()

    def load(self):
        paths = [
            os.path.expanduser("~/.femtorc"),
            ".femtorc",
        ]
        for path in paths:
            if os.path.exists(path):
                self._parse(path)
                break

    def _parse(self, path):
        try:
            with open(path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip()
                        if key == "tab_size":
                            self.tab_size = max(1, int(val))
                        elif key == "smooth_scroll_margin":
                            self.smooth_scroll_margin = max(0, int(val))
                        elif key == "soft_wrap":
                            self.soft_wrap = val.lower() in ("true", "1", "yes")
                        elif key == "ignore_case":
                            self.ignore_case = val.lower() in ("true", "1", "yes")
                        elif key == "regex_search":
                            self.regex_search = val.lower() in ("true", "1", "yes")
                        elif key == "show_line_numbers":
                            self.show_line_numbers = val.lower() in ("true", "1", "yes")
                        elif key == "syntax_highlight":
                            self.syntax_highlight = val.lower() in ("true", "1", "yes")
                        elif key == "mouse":
                            self.mouse = val.lower() in ("true", "1", "yes")
                        elif key == "make_backup":
                            self.make_backup = val.lower() in ("true", "1", "yes")
                        elif key == "line_ending":
                            if val in ("auto", "lf", "crlf", "cr"):
                                self.line_ending = val
                        elif key == "final_newline":
                            self.final_newline = val.lower() in ("true", "1", "yes")
                        elif key == "auto_indent":
                            self.auto_indent = val.lower() in ("true", "1", "yes")
                        elif key == "wrap_at_word":
                            self.wrap_at_word = val.lower() in ("true", "1", "yes")
                        elif key == "system_clipboard":
                            self.system_clipboard = val.lower() in ("true", "1", "yes")
        except Exception:
            pass
