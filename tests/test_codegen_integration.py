"""
Integration tests for the Similang codegen pipeline.

These tests compile programs end-to-end and, when marked ``@pytest.mark.integration``,
actually execute them via MCJIT.  Non-integration tests only verify that valid
LLVM IR is produced.
"""
import pytest
from frontend.lexer import Lexer
from frontend.parser import Parser
from middle.sema import SemanticAnalyzer
from backend.codegen import Codegen
from util.executor import execute_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _compile(src: str):
    """Compile *src* through lex -> parse -> sema -> codegen. Return the module."""
    lex = Lexer(src)
    p = Parser(lex)
    prog = p.parse_program()
    assert not p.error_collector.has_errors(), \
        f"Parser errors: {[e.format() for e in p.error_collector.errors]}"
    sema = SemanticAnalyzer()
    ok, errors = sema.analyze(prog)
    assert ok, f"Sema errors: {errors}"
    cg = Codegen()
    module = cg.compile(prog)
    assert not cg.errors, f"Codegen errors: {cg.errors}"
    return module


def _run(src: str) -> int:
    """Full pipeline: compile + execute, return exit code."""
    module = _compile(src)
    return execute_module(module)


# ---------------------------------------------------------------------------
# IR generation (no execution)
# ---------------------------------------------------------------------------
class TestIRGeneration:
    def test_empty_main(self):
        module = _compile("fn main() -> int { return 0; }")
        ir = str(module)
        assert "define" in ir
        assert "main" in ir

    def test_let_variable_in_ir(self):
        module = _compile("fn main() -> int { let x: int = 42; return x; }")
        ir = str(module)
        assert "alloca" in ir

    def test_function_with_params_in_ir(self):
        src = "fn add(a: int, b: int) -> int { return a + b; }"
        module = _compile(src)
        ir = str(module)
        assert "define" in ir
        assert "add" in ir

    def test_type_alias_compiles(self):
        """Using i32 alias should produce identical IR to 'int'."""
        module = _compile("fn main() -> int { let x: i32 = 42; return x; }")
        ir = str(module)
        assert "i32" in ir  # LLVM IR uses i32 natively

    def test_float_alias_compiles(self):
        module = _compile("fn main() -> int { let f: f32 = 3.14; return 0; }")
        ir = str(module)
        assert "float" in ir

    def test_if_else_in_ir(self):
        src = "fn main() -> int { if (true) { return 1; } else { return 0; } }"
        module = _compile(src)
        ir = str(module)
        assert "if_then" in ir
        assert "if_else" in ir


# ---------------------------------------------------------------------------
# Execution tests (require MCJIT)
# ---------------------------------------------------------------------------
class TestExecution:
    @pytest.mark.integration
    def test_simple_return(self):
        assert _run("fn main() -> int { return 42; }") == 42

    @pytest.mark.integration
    def test_addition(self):
        src = """
        fn main() -> int {
            let x: int = 40;
            let y: int = 2;
            return x + y;
        }"""
        assert _run(src) == 42

    @pytest.mark.integration
    def test_subtraction(self):
        src = "fn main() -> int { return 50 - 8; }"
        assert _run(src) == 42

    @pytest.mark.integration
    def test_multiplication(self):
        src = "fn main() -> int { return 6 * 7; }"
        assert _run(src) == 42

    @pytest.mark.integration
    def test_division(self):
        src = "fn main() -> int { return 84 / 2; }"
        assert _run(src) == 42

    @pytest.mark.integration
    def test_modulus(self):
        src = "fn main() -> int { return 10 % 3; }"
        assert _run(src) == 1

    @pytest.mark.integration
    def test_function_call(self):
        src = """
        fn add(a: int, b: int) -> int { return a + b; }
        fn main() -> int { return add(40, 2); }
        """
        assert _run(src) == 42

    @pytest.mark.integration
    def test_if_true_branch(self):
        src = """
        fn main() -> int {
            if (true) { return 1; } else { return 0; }
        }"""
        assert _run(src) == 1

    @pytest.mark.integration
    def test_if_false_branch(self):
        src = """
        fn main() -> int {
            if (false) { return 1; } else { return 0; }
        }"""
        assert _run(src) == 0

    @pytest.mark.integration
    def test_while_loop(self):
        src = """
        fn main() -> int {
            let i: int = 0;
            while (i < 10) { i++; }
            return i;
        }"""
        assert _run(src) == 10

    @pytest.mark.integration
    def test_for_loop(self):
        src = """
        fn main() -> int {
            let sum: int = 0;
            for (let i: int = 0; i < 5; i++) {
                sum += 1;
            }
            return sum;
        }"""
        assert _run(src) == 5

    @pytest.mark.integration
    def test_nested_function_calls(self):
        src = """
        fn double(x: int) -> int { return x * 2; }
        fn main() -> int { return double(double(10)); }
        """
        assert _run(src) == 40

    @pytest.mark.integration
    def test_type_alias_i32_executes(self):
        src = """
        fn main() -> int {
            let x: i32 = 40;
            let y: i32 = 2;
            return x + y;
        }"""
        assert _run(src) == 42

    @pytest.mark.integration
    def test_comparison_operators(self):
        src = """
        fn main() -> int {
            if (5 > 3) { return 1; } else { return 0; }
        }"""
        assert _run(src) == 1

    @pytest.mark.integration
    def test_compound_assignment(self):
        src = """
        fn main() -> int {
            let x: int = 10;
            x += 5;
            x -= 3;
            return x;
        }"""
        assert _run(src) == 12

    @pytest.mark.integration
    def test_negation(self):
        src = "fn main() -> int { return -(-42); }"
        assert _run(src) == 42
