"""
Source map for Similang.

Maps generated LLVM IR lines back to original source locations, enabling
debugging, profiling, and diagnostics that reference the original code.

The source map is a bidirectional index:
  - **forward** (source → IR):  ``source_to_ir[line]`` → list of IR line numbers
  - **reverse** (IR → source): ``ir_to_source[ir_line]`` → SourceMapping entry

The map is populated during code generation via ``record()`` calls and can be
serialized to JSON for tooling consumption.

Usage
-----
::

    smap = SourceMap(filename="test.simi", source_text=src)
    # ... during codegen, call smap.record(ir_line, source_loc, context) ...
    smap.finalize(str(module))
    smap.write_json("debug/test.simi.map.json")

Format
------
The JSON output follows a simple, human-readable structure::

    {
        "version": 1,
        "file": "test.simi",
        "source_root": "",
        "mappings": [
            {
                "ir_line": 5,
                "source_line": 2,
                "source_col": 4,
                "context": "let x: int = 42",
                "ir_text": "  %x = alloca i32"
            },
            ...
        ],
        "source_lines": { "1": "fn main() -> int {", ... },
        "stats": { "mapped_ir_lines": 12, "total_ir_lines": 30, "coverage": 0.40 }
    }
"""
from __future__ import annotations
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from frontend.ast import SourceLocation

logger = logging.getLogger("similang.sourcemap")


@dataclass
class SourceMapping:
    """A single IR-line → source-location mapping entry."""
    ir_line: int                     # 1-based line in the IR output
    source_line: int                 # 1-based line in the .simi source
    source_col: int = 0             # 0-based column in source
    context: str = ""               # human-readable description (e.g. "let x: int")
    ir_text: str = ""               # the IR instruction text (filled by finalize)

    def json(self) -> dict:
        d: dict = {
            "ir_line": self.ir_line,
            "source_line": self.source_line,
            "source_col": self.source_col,
        }
        if self.context:
            d["context"] = self.context
        if self.ir_text:
            d["ir_text"] = self.ir_text
        return d


class SourceMap:
    """
    Accumulates IR → source mappings during code generation and produces
    a serializable source map.

    Parameters
    ----------
    filename : str
        The source file path (stored in the map metadata).
    source_text : str
        The original source code (used to populate ``source_lines``).
    source_root : str
        Optional root prefix for source paths.
    """

    VERSION = 1

    def __init__(self, filename: str = "", source_text: str = "",
                 source_root: str = "") -> None:
        self.filename = filename
        self.source_root = source_root
        self._source_lines: List[str] = source_text.splitlines() if source_text else []

        # Core data: list of mappings (appended in IR-emission order)
        self._mappings: List[SourceMapping] = []

        # Indices (rebuilt by finalize)
        self.ir_to_source: Dict[int, SourceMapping] = {}
        self.source_to_ir: Dict[int, List[int]] = {}

        # Counter for the *next* expected IR line (set during codegen)
        self._pending_loc: Optional[SourceLocation] = None
        self._pending_context: str = ""

    # ------------------------------------------------------------------
    # Recording API  (called by codegen)
    # ------------------------------------------------------------------
    def record(self, ir_line: int, loc: SourceLocation,
               context: str = "") -> None:
        """
        Record a mapping from an IR line number to a source location.

        Parameters
        ----------
        ir_line : int
            1-based line number in the emitted IR text.
        loc : SourceLocation
            The AST node's source position.
        context : str
            Optional human-readable label (e.g. ``"let x: int = 42"``).
        """
        if not loc or loc.line <= 0:
            return
        entry = SourceMapping(
            ir_line=ir_line,
            source_line=loc.line,
            source_col=loc.col,
            context=context,
        )
        self._mappings.append(entry)

    def set_pending(self, loc: SourceLocation, context: str = "") -> None:
        """
        Stage a source location to be associated with the *next* IR
        instruction emitted.  Used when the exact IR line is not yet known.
        """
        if loc and loc.line > 0:
            self._pending_loc = loc
            self._pending_context = context

    def flush_pending(self, ir_line: int) -> None:
        """Commit the pending location (if any) for the given IR line."""
        if self._pending_loc:
            self.record(ir_line, self._pending_loc, self._pending_context)
            self._pending_loc = None
            self._pending_context = ""

    # ------------------------------------------------------------------
    # Finalize — call after codegen with the full IR text
    # ------------------------------------------------------------------
    def finalize(self, ir_text: str) -> None:
        """
        Post-process the recorded mappings:
          1. Populate ``ir_text`` on each entry.
          2. Build the forward/reverse indices.
          3. Deduplicate (keep first mapping per IR line).
        """
        ir_lines = ir_text.splitlines()

        # Deduplicate: keep first mapping per ir_line
        seen: set[int] = set()
        deduped: List[SourceMapping] = []
        for m in self._mappings:
            if m.ir_line not in seen:
                seen.add(m.ir_line)
                deduped.append(m)
        self._mappings = deduped

        # Fill ir_text for each mapping
        for m in self._mappings:
            idx = m.ir_line - 1
            if 0 <= idx < len(ir_lines):
                m.ir_text = ir_lines[idx].rstrip()

        # Build indices
        self.ir_to_source.clear()
        self.source_to_ir.clear()
        for m in self._mappings:
            self.ir_to_source[m.ir_line] = m
            self.source_to_ir.setdefault(m.source_line, []).append(m.ir_line)

        logger.debug("Source map finalized: %d mappings, %d/%d IR lines covered",
                      len(self._mappings), len(self.ir_to_source),
                      len(ir_lines))

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def lookup_ir(self, ir_line: int) -> Optional[SourceMapping]:
        """Look up the source mapping for a given IR line."""
        return self.ir_to_source.get(ir_line)

    def lookup_source(self, source_line: int) -> List[int]:
        """Return IR line numbers that correspond to a source line."""
        return self.source_to_ir.get(source_line, [])

    @property
    def mappings(self) -> List[SourceMapping]:
        return list(self._mappings)

    @property
    def coverage(self) -> float:
        """Fraction of IR lines that have a source mapping (0.0 – 1.0)."""
        if not self.ir_to_source:
            return 0.0
        max_ir = max(self.ir_to_source.keys()) if self.ir_to_source else 1
        return len(self.ir_to_source) / max_ir if max_ir else 0.0

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------
    def to_json(self) -> dict:
        """Return a JSON-serializable dict of the source map."""
        mapped = len(self.ir_to_source)
        max_ir = max(self.ir_to_source.keys()) if self.ir_to_source else 0
        return {
            "version": self.VERSION,
            "file": self.filename,
            "source_root": self.source_root,
            "mappings": [m.json() for m in self._mappings],
            "source_lines": {
                str(i + 1): line
                for i, line in enumerate(self._source_lines)
            },
            "stats": {
                "mapped_ir_lines": mapped,
                "total_ir_lines": max_ir,
                "coverage": round(mapped / max_ir, 4) if max_ir else 0.0,
            },
        }

    def write_json(self, path: str | Path, *, pretty: bool = True) -> Path:
        """Write the source map to a JSON file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(self.to_json(), f, indent=2 if pretty else None)
        logger.info("Source map written to %s", p)
        return p

    def format_table(self) -> str:
        """
        Return a human-readable table of mappings for terminal display.

        Example::

            IR Line │ Source │ Context
            ────────┼────────┼─────────────────
                  5 │   2:4  │ let x: int = 42
                  8 │   3:4  │ return x
        """
        if not self._mappings:
            return "(no source mappings recorded)"

        lines: list[str] = []
        hdr = f"{'IR Line':>8} | {'Source':>8} | Context"
        sep = f"{'-' * 8}-+-{'-' * 8}-+{'-' * 30}"
        lines.append(hdr)
        lines.append(sep)
        for m in sorted(self._mappings, key=lambda e: e.ir_line):
            src = f"{m.source_line}:{m.source_col}"
            lines.append(f"{m.ir_line:>8} | {src:>8} | {m.context}")
        return "\n".join(lines)

    def __len__(self) -> int:
        return len(self._mappings)

    def __repr__(self) -> str:
        return f"SourceMap({self.filename!r}, {len(self._mappings)} mappings)"
