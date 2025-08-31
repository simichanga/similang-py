from dataclasses import dataclass
from typing import Optional, List
from enum import Enum

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


class ErrorCollector:
    """Centralized error collection and reporting."""

    def __init__(self):
        self.errors: List[CompilerError] = []
        self.warnings: List[CompilerError] = []

    def add_error(self, message: str, **kwargs):
        err = CompilerError(ErrorLevel.ERROR, message, **kwargs)
        self.errors.append(err)

    def add_warning(self, message: str, **kwargs):
        warn = CompilerError(ErrorLevel.WARNING, message, **kwargs)
        self.warnings.append(warn)

    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def report(self):
        """Print all collected errors and warnings."""
        for warn in self.warnings:
            print(warn.format())
        for err in self.errors:
            print(err.format())

    def clear(self):
        self.errors.clear()
        self.warnings.clear()