"""
Tests for the Similang LSP analysis module.

Covers:
  - Diagnostic generation (parse errors, sema errors, clean programs)
  - Document symbol extraction (functions, variables, parameters)
  - Hover info (type information)
  - Definition locations
  - Usage tracking (for go-to-definition)
  - Completion scope symbols
  - Edge cases (empty doc, syntax crash, multiple functions)
"""
from __future__ import annotations

import pytest
from lsprotocol import types as lsp

from lsp.analysis import AnalysisResult, analyze_document


URI = "file:///test.simi"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _analyze(src: str) -> AnalysisResult:
    return analyze_document(src, URI)


# ===========================================================================
# 1. Diagnostics
# ===========================================================================
class TestDiagnostics:
    def test_clean_program_no_diagnostics(self):
        r = _analyze("fn main() -> int { return 0; }")
        assert len(r.diagnostics) == 0

    def test_parse_error_reported(self):
        r = _analyze("fn main( { return 0; }")
        assert len(r.diagnostics) > 0
        assert any("ERROR" in d.message for d in r.diagnostics)

    def test_sema_error_undeclared(self):
        r = _analyze("fn main() -> int { return x; }")
        assert len(r.diagnostics) >= 1
        assert any("undeclared" in d.message.lower() or "Undeclared" in d.message
                    for d in r.diagnostics)

    def test_sema_error_type_mismatch(self):
        r = _analyze("fn main() -> int { let x: int = true; return x; }")
        # bool cannot be assigned to int
        assert len(r.diagnostics) >= 1

    def test_diagnostics_are_error_severity(self):
        r = _analyze("fn main() -> int { return x; }")
        for d in r.diagnostics:
            assert d.severity == lsp.DiagnosticSeverity.Error

    def test_diagnostic_source_is_similang(self):
        r = _analyze("fn main() -> int { return x; }")
        for d in r.diagnostics:
            assert d.source == "similang"

    def test_empty_document(self):
        r = _analyze("")
        assert len(r.diagnostics) == 0
        assert len(r.symbols) == 0

    def test_whitespace_only(self):
        r = _analyze("   \n  \n  ")
        assert len(r.diagnostics) == 0


# ===========================================================================
# 2. Document Symbols
# ===========================================================================
class TestDocumentSymbols:
    def test_function_symbol(self):
        r = _analyze("fn main() -> int { return 0; }")
        assert len(r.symbols) == 1
        sym = r.symbols[0]
        assert sym.name == "main"
        assert sym.kind == lsp.SymbolKind.Function
        assert "int" in sym.detail

    def test_function_with_params(self):
        r = _analyze("fn add(a: int, b: int) -> int { return a + b; }")
        sym = r.symbols[0]
        assert sym.name == "add"
        assert "a: int" in sym.detail
        assert "b: int" in sym.detail

    def test_function_children_include_params(self):
        r = _analyze("fn add(a: int, b: float) -> int { return 0; }")
        sym = r.symbols[0]
        assert sym.children is not None
        param_names = [c.name for c in sym.children]
        assert "a" in param_names
        assert "b" in param_names

    def test_function_children_include_locals(self):
        r = _analyze("fn main() -> int { let x: int = 1; return x; }")
        sym = r.symbols[0]
        assert sym.children is not None
        child_names = [c.name for c in sym.children]
        assert "x" in child_names

    def test_multiple_functions(self):
        src = """
fn add(a: int, b: int) -> int { return a + b; }
fn main() -> int { return add(1, 2); }
"""
        r = _analyze(src)
        names = [s.name for s in r.symbols]
        assert "add" in names
        assert "main" in names

    def test_variable_detail_is_type(self):
        r = _analyze("fn main() -> int { let x: float = 1.0; return 0; }")
        sym = r.symbols[0]
        x_sym = next(c for c in sym.children if c.name == "x")
        assert x_sym.detail == "float"


# ===========================================================================
# 3. Hover
# ===========================================================================
class TestHover:
    def test_function_hover(self):
        r = _analyze("fn main() -> int { return 0; }")
        fn_hovers = [h for h in r.hovers if "fn(" in h.contents.value]
        assert len(fn_hovers) >= 1
        assert "int" in fn_hovers[0].contents.value

    def test_variable_hover(self):
        r = _analyze("fn main() -> int { let x: int = 42; return x; }")
        var_hovers = [h for h in r.hovers if "let x" in h.contents.value]
        assert len(var_hovers) >= 1
        assert "int" in var_hovers[0].contents.value

    def test_hover_has_range(self):
        r = _analyze("fn main() -> int { return 0; }")
        for h in r.hovers:
            assert h.range is not None

    def test_hover_is_markdown(self):
        r = _analyze("fn main() -> int { return 0; }")
        for h in r.hovers:
            assert h.contents.kind == lsp.MarkupKind.Markdown


# ===========================================================================
# 4. Definitions
# ===========================================================================
class TestDefinitions:
    def test_function_definition_registered(self):
        r = _analyze("fn main() -> int { return 0; }")
        assert "main" in r.definitions

    def test_variable_definition_registered(self):
        r = _analyze("fn main() -> int { let abc: int = 1; return abc; }")
        assert "abc" in r.definitions

    def test_definition_has_uri(self):
        r = _analyze("fn main() -> int { return 0; }")
        loc = r.definitions["main"]
        assert loc.uri == URI

    def test_definition_has_range(self):
        r = _analyze("fn main() -> int { return 0; }")
        loc = r.definitions["main"]
        assert loc.range is not None


# ===========================================================================
# 5. Usages (for go-to-definition)
# ===========================================================================
class TestUsages:
    def test_variable_usage_tracked(self):
        r = _analyze("fn main() -> int { let x: int = 1; return x; }")
        assert "x" in r.usages
        assert len(r.usages["x"]) >= 1

    def test_function_call_usage_tracked(self):
        src = "fn add(a: int, b: int) -> int { return a + b; }\nfn main() -> int { return add(1, 2); }"
        r = _analyze(src)
        assert "add" in r.usages
        assert len(r.usages["add"]) >= 1

    def test_usage_has_range(self):
        r = _analyze("fn main() -> int { let x: int = 1; return x; }")
        for rng in r.usages.get("x", []):
            assert isinstance(rng, lsp.Range)


# ===========================================================================
# 6. Completion scope symbols
# ===========================================================================
class TestScopeSymbols:
    def test_function_in_scope(self):
        r = _analyze("fn main() -> int { return 0; }")
        assert "main" in r.scope_symbols
        assert r.scope_symbols["main"]["kind"] == "function"

    def test_variable_in_scope(self):
        r = _analyze("fn main() -> int { let x: int = 1; return x; }")
        assert "x" in r.scope_symbols
        assert r.scope_symbols["x"]["kind"] == "variable"
        assert r.scope_symbols["x"]["type"] == "int"

    def test_params_in_scope(self):
        r = _analyze("fn add(a: int, b: float) -> int { return 0; }")
        assert "a" in r.scope_symbols
        assert r.scope_symbols["a"]["type"] == "int"
        assert "b" in r.scope_symbols
        assert r.scope_symbols["b"]["type"] == "float"


# ===========================================================================
# 7. Complex programs
# ===========================================================================
class TestComplexPrograms:
    def test_multiline_with_control_flow(self):
        src = """fn main() -> int {
  let x: int = 10;
  let y: int = 0;
  while x > 0 {
    y += x;
    x--;
  }
  return y;
}"""
        r = _analyze(src)
        assert len(r.diagnostics) == 0
        assert len(r.symbols) == 1
        assert "x" in r.scope_symbols
        assert "y" in r.scope_symbols

    def test_for_loop(self):
        src = """fn main() -> int {
  let sum: int = 0;
  for (let i: int = 0; i < 10; i++) {
    sum += i;
  }
  return sum;
}"""
        r = _analyze(src)
        assert len(r.diagnostics) == 0

    def test_if_else(self):
        src = """fn main() -> int {
  let x: int = 5;
  if (x > 3) {
    return 1;
  } else {
    return 0;
  }
}"""
        r = _analyze(src)
        assert len(r.diagnostics) == 0

    def test_multiple_functions_with_calls(self):
        src = """fn square(n: int) -> int {
  return n * n;
}

fn main() -> int {
  let result: int = square(5);
  return result;
}"""
        r = _analyze(src)
        assert len(r.diagnostics) == 0
        names = [s.name for s in r.symbols]
        assert "square" in names
        assert "main" in names
        assert "square" in r.usages  # called in main

    def test_string_program(self):
        src = 'fn main() -> int { printf("hello\\n"); return 0; }'
        r = _analyze(src)
        # printf is a builtin, should not cause sema error for undeclared
        assert not any("printf" in d.message and "undeclared" in d.message.lower()
                       for d in r.diagnostics)
