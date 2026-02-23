"""
Shared pytest configuration and fixtures for Similang tests.
"""
from __future__ import annotations

import io
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import pytest

from util.config import Config
from util.debug import dump_ast, dump_tokens
from util.diagnostics import DiagnosticEngine


# ---------------------------------------------------------------------------
# Global test config
# ---------------------------------------------------------------------------
Config.DEBUG = False          # keep tests quiet by default
Config.PARSER_DEBUG = False
Config.CODEGEN_DEBUG = False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def diag():
    """Provide a fresh DiagnosticEngine that writes to an in-memory buffer."""
    buf = io.StringIO()
    engine = DiagnosticEngine(source_text="", stream=buf, color=False)
    engine._buf = buf          # expose for assertions
    return engine


@dataclass
class DebugDumper:
    """Collects AST / token dump requests; writes them only if the test fails."""
    _asts: list = field(default_factory=list)
    _token_lexers: list = field(default_factory=list)

    def register_ast(self, program, *, name: str = "ast_dump") -> None:
        self._asts.append((program, name))

    def register_tokens(self, lexer, *, name: str = "token_dump") -> None:
        self._token_lexers.append((lexer, name))

    def flush(self) -> None:
        old_debug = Config.DEBUG
        Config.DEBUG = True
        try:
            for prog, name in self._asts:
                dump_ast(prog, filename=name)
            for lex, name in self._token_lexers:
                dump_tokens(lex, filename=name)
        finally:
            Config.DEBUG = old_debug


@pytest.fixture
def debug_dumper(request):
    """Fixture that dumps AST/tokens only when the test fails."""
    dumper = DebugDumper()
    yield dumper
    # Teardown: dump if the test failed
    rep = getattr(request.node, "rep_call", None)
    if rep and rep.failed:
        dumper.flush()


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Store test result on the item so fixtures can inspect it during teardown."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the tests/fixtures/ directory."""
    return Path(__file__).parent / "fixtures"

