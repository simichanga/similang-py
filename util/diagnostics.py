"""
Compiler Diagnostics Engine for Similang.

Provides structured, coloured diagnostic output modelled after modern compilers
(clang, rustc, gcc).  Supports errors, warnings, notes, and hints with optional
source-location context and caret highlighting.

Usage
-----
    from util.diagnostics import DiagnosticEngine, Severity, SourceLocation

    diag = DiagnosticEngine(source_text=src, filename="main.simi")
    diag.emit(Severity.ERROR, "undeclared variable 'x'",
              loc=SourceLocation(line=5, col=10))
    diag.emit(Severity.WARNING, "unused variable 'y'",
              loc=SourceLocation(line=3, col=5))
    ...
    diag.summary()         # e.g.  "2 errors, 1 warning generated."
    diag.has_errors()       # True
"""
from __future__ import annotations

import sys
import os
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, TextIO


# ---------------------------------------------------------------------------
# Severity
# ---------------------------------------------------------------------------
class Severity(Enum):
    """Diagnostic severity levels, ordered from least to most severe."""
    HINT = auto()
    NOTE = auto()
    WARNING = auto()
    ERROR = auto()
    FATAL = auto()


# ---------------------------------------------------------------------------
# Source Location
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SourceLocation:
    """Identifies a position in a source file."""
    line: int = 0        # 1-based
    col: int = 0         # 1-based; 0 = unknown column
    end_col: int = 0     # for range highlighting (0 = single char)
    filename: Optional[str] = None

    def __str__(self) -> str:
        parts: list[str] = []
        if self.filename:
            parts.append(self.filename)
        if self.line:
            parts.append(str(self.line))
            if self.col:
                parts.append(str(self.col))
        return ":".join(parts) if parts else "<unknown>"


# ---------------------------------------------------------------------------
# Diagnostic record
# ---------------------------------------------------------------------------
@dataclass
class Diagnostic:
    """A single diagnostic message."""
    severity: Severity
    message: str
    loc: Optional[SourceLocation] = None
    hint: Optional[str] = None               # supplementary hint text
    notes: List[str] = field(default_factory=list)

    def format(self, *, color: bool = False, source_lines: Optional[List[str]] = None) -> str:
        """Return a human-readable, optionally-coloured diagnostic string."""
        buf: list[str] = []

        # Location prefix  (e.g. "main.simi:5:10: ")
        loc_str = str(self.loc) + ": " if self.loc else ""

        # Severity tag
        tag = self.severity.name.lower()
        if color:
            tag = _colorize(tag, self.severity)

        buf.append(f"{loc_str}{tag}: {self.message}")

        # Source context + caret
        if source_lines and self.loc and self.loc.line > 0:
            idx = self.loc.line - 1
            if 0 <= idx < len(source_lines):
                line_text = source_lines[idx].rstrip("\n")
                line_no_str = f"{self.loc.line:>5} | "
                buf.append(f"{line_no_str}{line_text}")
                if self.loc.col > 0:
                    caret_pad = " " * (len(line_no_str) + self.loc.col - 1)
                    span = max(1, self.loc.end_col - self.loc.col) if self.loc.end_col else 1
                    caret = "^" + "~" * (span - 1)
                    if color:
                        caret = _colorize(caret, self.severity)
                    buf.append(f"{caret_pad}{caret}")

        # Hint
        if self.hint:
            hint_prefix = "hint" if not color else _colorize("hint", Severity.HINT)
            buf.append(f"  = {hint_prefix}: {self.hint}")

        # Notes
        for note in self.notes:
            note_prefix = "note" if not color else _colorize("note", Severity.NOTE)
            buf.append(f"  = {note_prefix}: {note}")

        return "\n".join(buf)


# ---------------------------------------------------------------------------
# Diagnostic Engine
# ---------------------------------------------------------------------------
class DiagnosticEngine:
    """
    Central hub for all compiler diagnostics.

    Typical lifecycle:
        1. Construct with the source text (and optional filename).
        2. Various compiler phases call ``emit()`` to report issues.
        3. After each phase, call ``has_errors()`` to decide whether to
           continue or abort.
        4. At the very end, call ``summary()`` to print a one-line tally.
    """

    def __init__(
        self,
        source_text: str = "",
        filename: Optional[str] = None,
        *,
        stream: TextIO = sys.stderr,
        color: Optional[bool] = None,
    ) -> None:
        self._source_lines: List[str] = source_text.splitlines(keepends=True) if source_text else []
        self._filename: Optional[str] = filename
        self._stream: TextIO = stream
        self._color: bool = color if color is not None else _supports_color(stream)

        self._diagnostics: List[Diagnostic] = []
        self._error_count: int = 0
        self._warning_count: int = 0
        self._note_count: int = 0
        self._max_errors: int = 50  # stop emitting after this many errors

    # -- configuration -------------------------------------------------------
    @property
    def max_errors(self) -> int:
        return self._max_errors

    @max_errors.setter
    def max_errors(self, value: int) -> None:
        self._max_errors = max(1, value)

    # -- emitting ------------------------------------------------------------
    def emit(
        self,
        severity: Severity,
        message: str,
        *,
        loc: Optional[SourceLocation] = None,
        hint: Optional[str] = None,
        notes: Optional[List[str]] = None,
    ) -> None:
        """Emit a diagnostic and print it to the output stream."""
        # Fill in filename from engine default if not on the loc
        if loc and not loc.filename and self._filename:
            loc = SourceLocation(
                line=loc.line,
                col=loc.col,
                end_col=loc.end_col,
                filename=self._filename,
            )

        diag = Diagnostic(
            severity=severity,
            message=message,
            loc=loc,
            hint=hint,
            notes=notes or [],
        )
        self._diagnostics.append(diag)

        match severity:
            case Severity.ERROR | Severity.FATAL:
                self._error_count += 1
            case Severity.WARNING:
                self._warning_count += 1
            case Severity.NOTE | Severity.HINT:
                self._note_count += 1

        # Render and print
        if self._error_count <= self._max_errors:
            rendered = diag.format(color=self._color, source_lines=self._source_lines)
            self._stream.write(rendered + "\n")
        elif self._error_count == self._max_errors + 1:
            self._stream.write(
                f"... too many errors ({self._error_count}); further diagnostics suppressed.\n"
            )

        if severity == Severity.FATAL:
            self.summary()
            raise SystemExit(1)

    # -- convenience shortcuts -----------------------------------------------
    def error(self, message: str, **kwargs) -> None:
        self.emit(Severity.ERROR, message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        self.emit(Severity.WARNING, message, **kwargs)

    def note(self, message: str, **kwargs) -> None:
        self.emit(Severity.NOTE, message, **kwargs)

    def hint(self, message: str, **kwargs) -> None:
        self.emit(Severity.HINT, message, **kwargs)

    # -- queries -------------------------------------------------------------
    def has_errors(self) -> bool:
        return self._error_count > 0

    @property
    def error_count(self) -> int:
        return self._error_count

    @property
    def warning_count(self) -> int:
        return self._warning_count

    @property
    def diagnostics(self) -> List[Diagnostic]:
        """All diagnostics collected so far (read-only snapshot)."""
        return list(self._diagnostics)

    # -- summary -------------------------------------------------------------
    def summary(self) -> str:
        """Print and return a summary line (e.g. '2 errors, 1 warning generated.')."""
        parts: list[str] = []
        if self._error_count:
            parts.append(f"{self._error_count} error{'s' if self._error_count != 1 else ''}")
        if self._warning_count:
            parts.append(f"{self._warning_count} warning{'s' if self._warning_count != 1 else ''}")
        if not parts:
            line = "no diagnostics."
        else:
            line = ", ".join(parts) + " generated."
        self._stream.write(line + "\n")
        return line

    def reset(self) -> None:
        """Reset all counters and stored diagnostics."""
        self._diagnostics.clear()
        self._error_count = 0
        self._warning_count = 0
        self._note_count = 0


# ---------------------------------------------------------------------------
# ANSI colour helpers
# ---------------------------------------------------------------------------
_ANSI_RESET = "\033[0m"

_SEVERITY_COLORS: dict[Severity, str] = {
    Severity.HINT:    "\033[36m",       # cyan
    Severity.NOTE:    "\033[36m",       # cyan
    Severity.WARNING: "\033[1;33m",     # bold yellow
    Severity.ERROR:   "\033[1;31m",     # bold red
    Severity.FATAL:   "\033[1;35m",     # bold magenta
}


def _colorize(text: str, severity: Severity) -> str:
    code = _SEVERITY_COLORS.get(severity, "")
    return f"{code}{text}{_ANSI_RESET}" if code else text


def _supports_color(stream: TextIO) -> bool:
    """Heuristic: emit colour when writing to a real terminal."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    try:
        return hasattr(stream, "isatty") and stream.isatty()
    except Exception:
        return False
