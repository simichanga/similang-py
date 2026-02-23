"""
Backward-compatible error types that delegate to the new DiagnosticEngine.

The ``ErrorCollector`` is kept as a lightweight adapter so that existing code
(parser, etc.) can continue calling ``add_error`` / ``add_warning`` while the
real work is done by ``DiagnosticEngine``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List
from enum import Enum

from util.diagnostics import DiagnosticEngine, Severity, SourceLocation


class ErrorLevel(Enum):
    WARNING = "warning"
    ERROR = "error"
    FATAL = "fatal"


@dataclass
class CompilerError:
    level: ErrorLevel
    message: str
    line: Optional[int] = None
    column: Optional[int] = None
    file: Optional[str] = None
    context: Optional[str] = None

    def format(self) -> str:
        loc = ""
        if self.file:
            loc = f"{self.file}:"
        if self.line:
            loc += f"{self.line}:"
        if self.column:
            loc += f"{self.column}:"

        prefix = f"[{self.level.value.upper()}]"
        if loc:
            return f"{prefix} {loc} {self.message}"
        return f"{prefix} {self.message}"


_LEVEL_TO_SEVERITY = {
    ErrorLevel.WARNING: Severity.WARNING,
    ErrorLevel.ERROR:   Severity.ERROR,
    ErrorLevel.FATAL:   Severity.FATAL,
}


class ErrorCollector:
    """Centralized error collection and reporting.

    If a ``DiagnosticEngine`` is supplied, every collected error/warning is
    forwarded to it automatically.
    """

    def __init__(self, diag: Optional[DiagnosticEngine] = None):
        self.errors: List[CompilerError] = []
        self.warnings: List[CompilerError] = []
        self._diag = diag

    # -- collection ----------------------------------------------------------
    def add_error(self, message: str, *, line: Optional[int] = None,
                  column: Optional[int] = None, file: Optional[str] = None,
                  hint: Optional[str] = None, **kwargs) -> None:
        err = CompilerError(ErrorLevel.ERROR, message, line=line, column=column, file=file)
        self.errors.append(err)
        if self._diag:
            loc = SourceLocation(line=line or 0, col=column or 0) if line else None
            self._diag.error(message, loc=loc, hint=hint)

    def add_warning(self, message: str, *, line: Optional[int] = None,
                    column: Optional[int] = None, file: Optional[str] = None,
                    hint: Optional[str] = None, **kwargs) -> None:
        warn = CompilerError(ErrorLevel.WARNING, message, line=line, column=column, file=file)
        self.warnings.append(warn)
        if self._diag:
            loc = SourceLocation(line=line or 0, col=column or 0) if line else None
            self._diag.warning(message, loc=loc, hint=hint)

    # -- queries -------------------------------------------------------------
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    # -- output --------------------------------------------------------------
    def report(self) -> None:
        """Print all collected errors and warnings to stderr."""
        for warn in self.warnings:
            print(warn.format())
        for err in self.errors:
            print(err.format())

    def clear(self) -> None:
        self.errors.clear()
        self.warnings.clear()