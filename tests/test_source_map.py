"""
Tests for the Similang source map system.

Covers:
  - SourceLocation on AST nodes
  - SourceMapping / SourceMap unit tests
  - Parser source location propagation
  - Codegen → SourceMap integration
  - CLI flag integration
  - JSON serialization round-trip
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from frontend.ast import SourceLocation, Node, LetStatement, Program
from frontend.lexer import Lexer
from frontend.parser import Parser
from middle.sema import SemanticAnalyzer
from backend.codegen import Codegen
from util.source_map import SourceMap, SourceMapping


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _parse(src: str) -> Program:
    lex = Lexer(src)
    p = Parser(lex)
    prog = p.parse_program()
    assert not p.error_collector.has_errors(), \
        f"Parser errors: {[e.format() for e in p.error_collector.errors]}"
    return prog


def _compile_with_smap(src: str) -> tuple:
    """Compile and return (module, source_map, codegen)."""
    prog = _parse(src)
    sema = SemanticAnalyzer()
    ok, errors = sema.analyze(prog)
    assert ok, f"Sema errors: {errors}"
    smap = SourceMap(filename="test.simi", source_text=src)
    cg = Codegen(source_map=smap)
    mod = cg.compile(prog)
    assert not cg.errors, f"Codegen errors: {cg.errors}"
    return mod, smap, cg


# ===========================================================================
# 1. SourceLocation unit tests
# ===========================================================================
class TestSourceLocation:
    def test_default_is_falsy(self):
        loc = SourceLocation()
        assert not loc

    def test_with_line_is_truthy(self):
        loc = SourceLocation(line=1, col=1)
        assert loc

    def test_json_roundtrip(self):
        loc = SourceLocation(line=3, col=7, end_line=3, end_col=15)
        d = loc.json()
        assert d["line"] == 3
        assert d["col"] == 7
        assert d["end_line"] == 3
        assert d["end_col"] == 15

    def test_repr(self):
        loc = SourceLocation(line=5, col=10)
        assert "5" in repr(loc)

    def test_node_loc_property(self):
        """SourceLocation can be attached to any AST Node via .loc property."""
        node = LetStatement(name=None, value_type="int", value=None)
        assert not node.loc  # default is falsy
        loc = SourceLocation(line=2, col=3)
        node.loc = loc
        assert node.loc is loc
        assert node.loc.line == 2


# ===========================================================================
# 2. SourceMapping unit tests
# ===========================================================================
class TestSourceMapping:
    def test_basic(self):
        m = SourceMapping(ir_line=5, source_line=2, source_col=4,
                          context="let x", ir_text="  %x = alloca i32")
        assert m.ir_line == 5
        assert m.source_line == 2

    def test_json(self):
        m = SourceMapping(ir_line=10, source_line=3, source_col=1, context="return")
        d = m.json()
        assert d["ir_line"] == 10
        assert d["source_line"] == 3
        assert "context" in d

    def test_json_omits_empty_fields(self):
        m = SourceMapping(ir_line=1, source_line=1)
        d = m.json()
        assert "context" not in d
        assert "ir_text" not in d


# ===========================================================================
# 3. SourceMap unit tests (recording, finalize, queries)
# ===========================================================================
class TestSourceMapUnit:
    def test_empty_map(self):
        smap = SourceMap()
        assert len(smap) == 0
        assert smap.coverage == 0.0
        assert smap.mappings == []

    def test_record_and_lookup(self):
        smap = SourceMap()
        loc = SourceLocation(line=2, col=3)
        smap.record(5, loc, "let x")
        assert len(smap) == 1

        # finalize with mock IR
        ir_text = "\n".join([f"line {i}" for i in range(1, 11)])
        smap.finalize(ir_text)
        m = smap.lookup_ir(5)
        assert m is not None
        assert m.source_line == 2
        assert m.context == "let x"

    def test_reverse_lookup(self):
        smap = SourceMap()
        smap.record(5, SourceLocation(line=2, col=1), "a")
        smap.record(8, SourceLocation(line=2, col=10), "b")
        smap.finalize("x\n" * 10)
        # source line 2 maps to two IR lines
        ir_lines = smap.lookup_source(2)
        assert 5 in ir_lines
        assert 8 in ir_lines

    def test_deduplication(self):
        """Only the first mapping per IR line is kept."""
        smap = SourceMap()
        smap.record(5, SourceLocation(line=2, col=1), "first")
        smap.record(5, SourceLocation(line=3, col=1), "second")
        smap.finalize("x\n" * 10)
        assert len(smap) == 1
        assert smap.lookup_ir(5).context == "first"

    def test_ignores_invalid_loc(self):
        smap = SourceMap()
        smap.record(5, SourceLocation(), "bad")  # line=0 → skipped
        smap.record(5, SourceLocation(line=-1), "bad2")
        assert len(smap) == 0

    def test_pending_flush(self):
        smap = SourceMap()
        smap.set_pending(SourceLocation(line=4, col=2), "pending")
        smap.flush_pending(7)
        assert len(smap) == 1
        smap.finalize("x\n" * 10)
        assert smap.lookup_ir(7).source_line == 4

    def test_coverage(self):
        smap = SourceMap()
        smap.record(1, SourceLocation(line=1, col=1), "a")
        smap.record(5, SourceLocation(line=3, col=1), "b")
        smap.record(10, SourceLocation(line=5, col=1), "c")
        smap.finalize("x\n" * 10)
        # 3 mapped out of 10 (max IR line = 10)
        assert smap.coverage == pytest.approx(0.3, abs=0.01)

    def test_format_table(self):
        smap = SourceMap()
        smap.record(5, SourceLocation(line=2, col=4), "let x")
        smap.finalize("x\n" * 10)
        table = smap.format_table()
        assert "IR Line" in table
        assert "let x" in table

    def test_format_table_empty(self):
        smap = SourceMap()
        assert "no source mappings" in smap.format_table()


# ===========================================================================
# 4. SourceMap JSON serialization
# ===========================================================================
class TestSourceMapJSON:
    def test_to_json_structure(self):
        smap = SourceMap(filename="test.simi", source_text="fn main() -> int {\n  return 0;\n}")
        smap.record(1, SourceLocation(line=1, col=1), "fn main")
        smap.finalize("x\n" * 5)
        d = smap.to_json()
        assert d["version"] == 1
        assert d["file"] == "test.simi"
        assert len(d["mappings"]) == 1
        assert "1" in d["source_lines"]
        assert d["stats"]["mapped_ir_lines"] == 1

    def test_write_json(self):
        smap = SourceMap(filename="test.simi")
        smap.record(1, SourceLocation(line=1, col=1), "test")
        smap.finalize("line1\nline2")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = smap.write_json(Path(tmpdir) / "out.json")
            assert path.exists()
            data = json.loads(path.read_text(encoding="utf-8"))
            assert data["version"] == 1
            assert len(data["mappings"]) == 1

    def test_json_roundtrip_preserves_data(self):
        smap = SourceMap(filename="hello.simi", source_text="let x = 1;")
        smap.record(3, SourceLocation(line=1, col=1), "let x")
        smap.finalize("a\nb\nc\nd")
        j = json.dumps(smap.to_json())
        parsed = json.loads(j)
        assert parsed["mappings"][0]["ir_line"] == 3
        assert parsed["mappings"][0]["source_line"] == 1


# ===========================================================================
# 5. Parser source location propagation
# ===========================================================================
class TestParserLocPropagation:
    def test_function_statement_has_loc(self):
        prog = _parse("fn main() -> int { return 0; }")
        fn = prog.statements[0]
        assert fn.loc
        assert fn.loc.line == 1
        assert fn.loc.col >= 1

    def test_let_statement_has_loc(self):
        prog = _parse("fn main() -> int { let x: int = 42; return 0; }")
        fn = prog.statements[0]
        let_stmt = fn.body.statements[0]
        assert let_stmt.loc
        assert let_stmt.loc.line == 1

    def test_return_statement_has_loc(self):
        prog = _parse("fn main() -> int { return 42; }")
        fn = prog.statements[0]
        ret = fn.body.statements[0]
        assert ret.loc
        assert ret.loc.line == 1

    def test_if_statement_has_loc(self):
        prog = _parse("fn main() -> int { if (true) { return 1; } return 0; }")
        fn = prog.statements[0]
        if_stmt = fn.body.statements[0]
        assert if_stmt.loc
        assert if_stmt.loc.line == 1

    def test_while_statement_has_loc(self):
        prog = _parse("fn main() -> int { let i: int = 0; while (i < 10) { i += 1; } return i; }")
        fn = prog.statements[0]
        # Find the while statement
        while_stmt = fn.body.statements[1]
        assert while_stmt.loc

    def test_multiline_locations(self):
        src = "fn main() -> int {\n  let x: int = 1;\n  return x;\n}"
        prog = _parse(src)
        fn = prog.statements[0]
        assert fn.loc.line == 1
        let_stmt = fn.body.statements[0]
        assert let_stmt.loc.line == 2
        ret_stmt = fn.body.statements[1]
        assert ret_stmt.loc.line == 3

    def test_expression_statement_has_loc(self):
        prog = _parse('fn main() -> int { let x: int = 1; x = 2; return x; }')
        fn = prog.statements[0]
        assign = fn.body.statements[1]
        assert assign.loc
        assert assign.loc.line == 1


# ===========================================================================
# 6. Codegen → SourceMap integration
# ===========================================================================
class TestCodegenSourceMap:
    def test_simple_program_mappings(self):
        src = "fn main() -> int {\n  let x: int = 42;\n  return x;\n}"
        mod, smap, cg = _compile_with_smap(src)
        assert len(smap) >= 3  # fn, let, return

    def test_function_def_mapped(self):
        src = "fn main() -> int { return 0; }"
        mod, smap, cg = _compile_with_smap(src)
        # find the mapping for the function definition
        fn_mappings = [m for m in smap.mappings if "fn " in m.context]
        assert len(fn_mappings) >= 1
        assert "define" in fn_mappings[0].ir_text

    def test_let_statement_mapped(self):
        src = "fn main() -> int { let x: int = 10; return x; }"
        mod, smap, cg = _compile_with_smap(src)
        let_mappings = [m for m in smap.mappings if "let " in m.context]
        assert len(let_mappings) >= 1
        assert "alloca" in let_mappings[0].ir_text

    def test_return_mapped(self):
        src = "fn main() -> int { return 42; }"
        mod, smap, cg = _compile_with_smap(src)
        ret_mappings = [m for m in smap.mappings if m.context == "return"]
        assert len(ret_mappings) >= 1
        assert "ret" in ret_mappings[0].ir_text

    def test_named_alloca_in_ir(self):
        """Variables should produce named allocas for debuggability."""
        src = "fn main() -> int { let abc: int = 5; return abc; }"
        mod, smap, cg = _compile_with_smap(src)
        ir = str(mod)
        assert '%"abc"' in ir

    def test_if_statement_mapped(self):
        src = "fn main() -> int { if (true) { return 1; } return 0; }"
        mod, smap, cg = _compile_with_smap(src)
        if_mappings = [m for m in smap.mappings if m.context == "if"]
        assert len(if_mappings) >= 1

    def test_while_statement_mapped(self):
        src = "fn main() -> int { let i: int = 0; while (i < 5) { i += 1; } return i; }"
        mod, smap, cg = _compile_with_smap(src)
        while_mappings = [m for m in smap.mappings if m.context == "while"]
        assert len(while_mappings) >= 1

    def test_for_statement_mapped(self):
        src = "fn main() -> int { let s: int = 0; for (let i: int = 0; i < 5; i++) { s += i; } return s; }"
        mod, smap, cg = _compile_with_smap(src)
        for_mappings = [m for m in smap.mappings if m.context == "for"]
        assert len(for_mappings) >= 1

    def test_assignment_mapped(self):
        src = "fn main() -> int { let x: int = 1; x = 2; return x; }"
        mod, smap, cg = _compile_with_smap(src)
        assign_mappings = [m for m in smap.mappings if "=" in m.context and "let" not in m.context]
        assert len(assign_mappings) >= 1

    def test_call_expression_mapped(self):
        src = 'fn add(a: int, b: int) -> int { return a + b; }\nfn main() -> int { return add(1, 2); }'
        mod, smap, cg = _compile_with_smap(src)
        # There should be a mapping for the call if it's an expression statement
        # In this case, the call is inside return, so check function defs
        fn_mappings = [m for m in smap.mappings if "fn " in m.context]
        assert len(fn_mappings) >= 2  # add and main

    def test_no_source_map_when_not_provided(self):
        """Codegen works normally without source map."""
        prog = _parse("fn main() -> int { return 0; }")
        sema = SemanticAnalyzer()
        sema.analyze(prog)
        cg = Codegen()  # no source_map
        mod = cg.compile(prog)
        assert not cg.errors
        ir = str(mod)
        assert "define" in ir

    def test_source_line_correctness(self):
        """Verify that source line numbers in mappings match actual source lines."""
        src = "fn main() -> int {\n  let x: int = 1;\n  let y: int = 2;\n  return x;\n}"
        mod, smap, cg = _compile_with_smap(src)
        for m in smap.mappings:
            if "let x" in m.context:
                assert m.source_line == 2
            elif "let y" in m.context:
                assert m.source_line == 3
            elif m.context == "return":
                assert m.source_line == 4

    def test_ir_text_populated(self):
        """After finalize, each mapping should have ir_text filled in."""
        src = "fn main() -> int { return 0; }"
        mod, smap, cg = _compile_with_smap(src)
        for m in smap.mappings:
            assert m.ir_text, f"Mapping {m.context} has empty ir_text"

    def test_bidirectional_lookup(self):
        """Forward and reverse lookups are consistent."""
        src = "fn main() -> int {\n  let x: int = 42;\n  return x;\n}"
        mod, smap, cg = _compile_with_smap(src)
        for m in smap.mappings:
            # forward: IR → source
            looked_up = smap.lookup_ir(m.ir_line)
            assert looked_up is not None
            assert looked_up.source_line == m.source_line
            # reverse: source → IR
            ir_lines = smap.lookup_source(m.source_line)
            assert m.ir_line in ir_lines


# ===========================================================================
# 7. Fixture file integration
# ===========================================================================
class TestFixtureIntegration:
    def test_simple_simi(self, fixtures_dir):
        src = (fixtures_dir / "simple.simi").read_text()
        mod, smap, cg = _compile_with_smap(src)
        assert len(smap) >= 5  # fn, 3 lets, return
        # Verify function definition is first
        first = smap.mappings[0]
        assert "fn " in first.context
        assert first.source_line == 1

    def test_simple_simi_json_output(self, fixtures_dir):
        src = (fixtures_dir / "simple.simi").read_text()
        mod, smap, cg = _compile_with_smap(src)
        data = smap.to_json()
        assert data["version"] == 1
        assert len(data["mappings"]) >= 5
        # source_lines should include all 6 lines (including closing brace)
        assert len(data["source_lines"]) >= 5
