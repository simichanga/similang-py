"""
Thorough unit tests for the Similang semantic analyser.
"""
import pytest
from frontend.lexer import Lexer
from frontend.parser import Parser
from middle.sema import SemanticAnalyzer
from middle.types import TypeSystem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _analyze(src: str):
    """Parse + analyze *src*; return (ok, errors, program)."""
    lex = Lexer(src)
    p = Parser(lex)
    prog = p.parse_program()
    assert not p.error_collector.has_errors(), \
        f"Parser errors: {[e.format() for e in p.error_collector.errors]}"
    sema = SemanticAnalyzer()
    ok, errors = sema.analyze(prog)
    return ok, errors, prog


def _ok(src: str):
    ok, errors, _ = _analyze(src)
    assert ok, f"Expected no sema errors, got: {errors}"


def _fails(src: str, *, match: str | None = None):
    ok, errors, _ = _analyze(src)
    assert not ok, "Expected sema errors but analysis succeeded"
    if match:
        assert any(match in e for e in errors), \
            f"Expected error containing {match!r}, got: {errors}"
    return errors


# ---------------------------------------------------------------------------
# Variable declarations
# ---------------------------------------------------------------------------
class TestLetStatementSema:
    def test_valid_let_int(self):
        _ok("fn main() -> int { let x: int = 5; return x; }")

    def test_valid_let_float(self):
        _ok("fn main() -> int { let f: float = 3.14; return 0; }")

    def test_valid_let_bool(self):
        _ok("fn main() -> int { let b: bool = true; return 0; }")

    def test_valid_let_string(self):
        _ok('fn main() -> int { let s: str = "hi"; return 0; }')

    def test_unknown_type_error(self):
        """Unknown types are rejected at the sema level (parser allows IDENT for struct types)."""
        _fails("fn main() -> int { let x: footype = 5; return 0; }",
               match="Unknown type")

    def test_type_mismatch_bool_to_int(self):
        _fails("fn main() -> int { let x: int = true; return 0; }",
               match="cannot assign")


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
class TestTypeAliasesSema:
    @pytest.mark.parametrize("alias", ["i32", "i64", "u32", "i8"])
    def test_integer_alias_let(self, alias):
        _ok(f"fn main() -> int {{ let x: {alias} = 42; return 0; }}")

    @pytest.mark.parametrize("alias", ["f32", "f64"])
    def test_float_alias_let(self, alias):
        _ok(f"fn main() -> int {{ let x: {alias} = 3.14; return 0; }}")

    def test_string_alias(self):
        _ok('fn main() -> int { let s: string = "hello"; return 0; }')

    def test_alias_resolves_for_assignment_compat(self):
        """i32 and int should be assignment-compatible (both resolve to int)."""
        _ok("fn main() -> int { let a: i32 = 5; let b: int = 10; return 0; }")

    def test_function_with_alias_param_and_return(self):
        _ok("fn add(a: i32, b: i32) -> i32 { return a + b; }")


# ---------------------------------------------------------------------------
# Undeclared identifiers
# ---------------------------------------------------------------------------
class TestUndeclaredIdentifiers:
    def test_undeclared_variable(self):
        _fails("fn main() -> int { return x; }", match="Undeclared identifier")

    def test_undeclared_in_expression(self):
        _fails("fn main() -> int { let a: int = 1; return a + b; }",
               match="Undeclared identifier")


# ---------------------------------------------------------------------------
# Function declarations
# ---------------------------------------------------------------------------
class TestFunctionSema:
    def test_basic_function(self):
        _ok("fn main() -> int { return 0; }")

    def test_function_with_parameters(self):
        _ok("fn add(a: int, b: int) -> int { return a + b; }")

    def test_unknown_return_type(self):
        """Unknown return types are rejected at the sema level (parser allows IDENT for struct types)."""
        _fails("fn bad() -> mystery { return 0; }",
               match="unknown return type")

    def test_unknown_param_type(self):
        """Unknown param types pass parsing but are rejected by sema."""
        _fails("fn bad(x: mystery) -> int { return 0; }",
               match="unknown type")

    def test_return_type_mismatch(self):
        _fails('fn bad() -> int { return "hello"; }',
               match="Return type mismatch")

    def test_void_return_with_value(self):
        _fails("fn bad() -> void { return 5; }",
               match="Return type mismatch")

    def test_return_outside_function(self):
        _fails("return 5;", match="Return statement outside")

    def test_recursive_function(self):
        """A function should be able to call itself."""
        _ok("fn fact(n: int) -> int { return n; }")

    def test_function_call_arity_mismatch(self):
        src = "fn add(a: int, b: int) -> int { return a + b; } fn main() -> int { return add(1); }"
        _fails(src, match="expects 2 args")

    def test_call_unknown_function(self):
        _fails("fn main() -> int { return unknown(1); }",
               match="unknown function")


# ---------------------------------------------------------------------------
# Infix / prefix / postfix expressions
# ---------------------------------------------------------------------------
class TestExpressionSema:
    def test_int_arithmetic(self):
        _ok("fn main() -> int { let a: int = 2 + 3 * 4; return a; }")

    def test_float_arithmetic(self):
        _ok("fn main() -> int { let a: float = 1.0 + 2.0; return 0; }")

    def test_mixed_numeric(self):
        """int + float should widen to float."""
        _ok("fn main() -> int { let a: float = 1 + 2.0; return 0; }")

    def test_invalid_operator_types(self):
        _fails('fn main() -> int { let a: int = 1 + "hello"; return 0; }',
               match="cannot apply")

    def test_prefix_negate_numeric(self):
        _ok("fn main() -> int { let a: int = -5; return a; }")

    def test_prefix_not_bool(self):
        _ok("fn main() -> int { let b: bool = !true; return 0; }")

    def test_prefix_not_on_int_fails(self):
        _fails("fn main() -> int { let b: bool = !5; return 0; }",
               match="expects bool")

    def test_postfix_on_identifier(self):
        _ok("fn main() -> int { let x: int = 0; x++; return x; }")

    def test_comparison_produces_bool(self):
        _ok("fn main() -> int { let b: bool = 1 < 2; return 0; }")


# ---------------------------------------------------------------------------
# Control flow
# ---------------------------------------------------------------------------
class TestControlFlowSema:
    def test_if_condition_must_be_bool(self):
        _fails("fn main() -> int { if (5) { return 0; } return 1; }",
               match="must be bool")

    def test_while_condition_must_be_bool(self):
        _fails("fn main() -> int { while 42 { return 0; } return 1; }",
               match="must be bool")

    def test_valid_if_else(self):
        _ok("fn main() -> int { if (true) { return 1; } else { return 0; } }")

    def test_valid_while(self):
        _ok("fn main() -> int { let i: int = 0; while (i < 10) { i++; } return i; }")

    def test_for_loop(self):
        _ok("fn main() -> int { for (let i: int = 0; i < 10; i++) { } return 0; }")


# ---------------------------------------------------------------------------
# Assignment
# ---------------------------------------------------------------------------
class TestAssignmentSema:
    def test_assign_to_undeclared(self):
        _fails("fn main() -> int { x = 5; return 0; }",
               match="Undeclared identifier")

    def test_valid_assignment(self):
        _ok("fn main() -> int { let x: int = 0; x = 5; return x; }")


# ---------------------------------------------------------------------------
# TypeSystem unit tests
# ---------------------------------------------------------------------------
class TestTypeSystemDirect:
    def setup_method(self):
        self.ts = TypeSystem()

    def test_canonical_types_exist(self):
        for name in ("int", "float", "bool", "str", "void"):
            assert self.ts.exists(name), f"{name} should exist"

    def test_aliases_exist(self):
        for alias in ("i32", "i64", "f32", "f64", "u8", "u16", "u32", "u64", "string", "char"):
            assert self.ts.exists(alias), f"alias '{alias}' should exist"

    def test_resolve_alias(self):
        assert self.ts.resolve_alias("i32") == "int"
        assert self.ts.resolve_alias("f32") == "float"
        assert self.ts.resolve_alias("string") == "str"
        assert self.ts.resolve_alias("int") == "int"  # canonical -> itself

    def test_get_ir_type_via_alias(self):
        int_ir = self.ts.get_ir_type("int")
        i32_ir = self.ts.get_ir_type("i32")
        assert int_ir == i32_ir

    def test_is_numeric_alias(self):
        assert self.ts.is_numeric("i32")
        assert self.ts.is_numeric("f64")
        assert not self.ts.is_numeric("bool")

    def test_can_assign_alias(self):
        assert self.ts.can_assign("int", "i32")
        assert self.ts.can_assign("i32", "int")

    def test_binary_result_alias(self):
        assert self.ts.binary_result_type("i32", "i32", "+") == "int"
        assert self.ts.binary_result_type("i32", "f32", "+") == "float"
        assert self.ts.binary_result_type("i32", "i32", "<") == "bool"

    def test_unknown_type_does_not_exist(self):
        assert not self.ts.exists("mystery")
