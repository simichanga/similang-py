"""
Tests for the AST-level optimizer and LLVM optimization pass integration.

Tests are grouped by pass:
- TestConstantFolding — integer/float/bool folding, division by zero safety
- TestDeadCodeElimination — unreachable-after-return, constant-true/false if, while(false)
- TestConstantPropagation — single-assignment substitution, mutation safety
- TestASTOptimizer — orchestrator behaviour, opt-levels, fixed-point iteration
- TestLLVMOptimization — LLVM pass manager integration via executor (integration)
"""
from __future__ import annotations

import pytest

from frontend.lexer import Lexer
from frontend.parser import Parser
from frontend import ast as A
from middle.sema import SemanticAnalyzer
from middle.optimizer import (
    ConstantFolding,
    DeadCodeElimination,
    ConstantPropagation,
    ASTOptimizer,
    OptStats,
)
from backend.codegen import Codegen
from util.config import Config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _parse(src: str) -> A.Program:
    """Parse source code into an AST program."""
    lexer = Lexer(src)
    parser = Parser(lexer)
    prog = parser.parse_program()
    assert not parser.error_collector.has_errors(), parser.error_collector.errors
    return prog


def _parse_and_sema(src: str) -> A.Program:
    """Parse + semantic analysis."""
    prog = _parse(src)
    sema = SemanticAnalyzer()
    ok, errors = sema.analyze(prog)
    assert ok, errors
    return prog


def _first_func(prog: A.Program) -> A.FunctionStatement:
    """Return the first FunctionStatement."""
    for s in prog.statements:
        if isinstance(s, A.FunctionStatement):
            return s
    raise AssertionError("No FunctionStatement found")


def _first_let_value(func: A.FunctionStatement) -> A.Expression:
    """Return the value expression of the first LetStatement inside a function body."""
    for s in func.body.statements:
        if isinstance(s, A.LetStatement):
            return s.value
    raise AssertionError("No LetStatement in function body")


def _return_value(func: A.FunctionStatement) -> A.Expression:
    """Return the return_value of the first ReturnStatement in a function body."""
    for s in func.body.statements:
        if isinstance(s, A.ReturnStatement):
            return s.return_value
    raise AssertionError("No ReturnStatement in function body")


# ===========================================================================
# Constant Folding
# ===========================================================================
class TestConstantFolding:

    def test_int_addition(self):
        prog = _parse("fn main() -> int { let x: int = 2 + 3; return x; }")
        fold = ConstantFolding()
        prog, stats = fold.run(prog)
        val = _first_let_value(_first_func(prog))
        assert isinstance(val, A.IntegerLiteral)
        assert val.value == 5
        assert stats.constants_folded >= 1

    def test_int_subtraction(self):
        prog = _parse("fn main() -> int { let x: int = 10 - 4; return x; }")
        fold = ConstantFolding()
        prog, _ = fold.run(prog)
        val = _first_let_value(_first_func(prog))
        assert isinstance(val, A.IntegerLiteral)
        assert val.value == 6

    def test_int_multiplication(self):
        prog = _parse("fn main() -> int { let x: int = 6 * 7; return x; }")
        fold = ConstantFolding()
        prog, _ = fold.run(prog)
        val = _first_let_value(_first_func(prog))
        assert isinstance(val, A.IntegerLiteral)
        assert val.value == 42

    def test_int_division(self):
        prog = _parse("fn main() -> int { let x: int = 10 / 3; return x; }")
        fold = ConstantFolding()
        prog, _ = fold.run(prog)
        val = _first_let_value(_first_func(prog))
        assert isinstance(val, A.IntegerLiteral)
        assert val.value == 3  # integer division

    def test_int_modulo(self):
        prog = _parse("fn main() -> int { let x: int = 10 % 3; return x; }")
        fold = ConstantFolding()
        prog, _ = fold.run(prog)
        val = _first_let_value(_first_func(prog))
        assert isinstance(val, A.IntegerLiteral)
        assert val.value == 1

    def test_division_by_zero_not_folded(self):
        prog = _parse("fn main() -> int { let x: int = 10 / 0; return x; }")
        fold = ConstantFolding()
        prog, stats = fold.run(prog)
        val = _first_let_value(_first_func(prog))
        # Should remain as InfixExpression, not folded
        assert isinstance(val, A.InfixExpression)
        assert stats.constants_folded == 0

    def test_float_addition(self):
        prog = _parse("fn main() -> int { let x: float = 1.5 + 2.5; return 0; }")
        fold = ConstantFolding()
        prog, stats = fold.run(prog)
        val = _first_let_value(_first_func(prog))
        assert isinstance(val, A.FloatLiteral)
        assert abs(val.value - 4.0) < 1e-9
        assert stats.constants_folded >= 1

    def test_float_division(self):
        prog = _parse("fn main() -> int { let x: float = 10.0 / 4.0; return 0; }")
        fold = ConstantFolding()
        prog, _ = fold.run(prog)
        val = _first_let_value(_first_func(prog))
        assert isinstance(val, A.FloatLiteral)
        assert abs(val.value - 2.5) < 1e-9

    def test_mixed_int_float_promotes(self):
        """int + float → FloatLiteral."""
        prog = _parse("fn main() -> int { let x: float = 2 + 3.0; return 0; }")
        fold = ConstantFolding()
        prog, _ = fold.run(prog)
        val = _first_let_value(_first_func(prog))
        assert isinstance(val, A.FloatLiteral)
        assert abs(val.value - 5.0) < 1e-9

    def test_int_comparison_less(self):
        prog = _parse("fn main() -> int { let x: bool = 2 < 5; return 0; }")
        fold = ConstantFolding()
        prog, _ = fold.run(prog)
        val = _first_let_value(_first_func(prog))
        assert isinstance(val, A.BooleanLiteral)
        assert val.value is True

    def test_int_comparison_eq_false(self):
        prog = _parse("fn main() -> int { let x: bool = 3 == 5; return 0; }")
        fold = ConstantFolding()
        prog, _ = fold.run(prog)
        val = _first_let_value(_first_func(prog))
        assert isinstance(val, A.BooleanLiteral)
        assert val.value is False

    def test_nested_constant_folding(self):
        """(2 + 3) * (4 + 1) → first fold inner, then outer."""
        prog = _parse("fn main() -> int { let x: int = (2 + 3) * (4 + 1); return x; }")
        fold = ConstantFolding()
        prog, stats = fold.run(prog)
        val = _first_let_value(_first_func(prog))
        assert isinstance(val, A.IntegerLiteral)
        assert val.value == 25
        assert stats.constants_folded >= 3  # 2+3, 4+1, 5*5

    def test_prefix_negate_int(self):
        prog = _parse("fn main() -> int { let x: int = -42; return x; }")
        fold = ConstantFolding()
        prog, stats = fold.run(prog)
        val = _first_let_value(_first_func(prog))
        assert isinstance(val, A.IntegerLiteral)
        assert val.value == -42

    def test_prefix_negate_float(self):
        prog = _parse("fn main() -> int { let x: float = -3.14; return 0; }")
        fold = ConstantFolding()
        prog, _ = fold.run(prog)
        val = _first_let_value(_first_func(prog))
        assert isinstance(val, A.FloatLiteral)
        assert abs(val.value - (-3.14)) < 1e-9

    def test_prefix_not_true(self):
        prog = _parse("fn main() -> int { let x: bool = !true; return 0; }")
        fold = ConstantFolding()
        prog, _ = fold.run(prog)
        val = _first_let_value(_first_func(prog))
        assert isinstance(val, A.BooleanLiteral)
        assert val.value is False

    def test_prefix_not_false(self):
        prog = _parse("fn main() -> int { let x: bool = !false; return 0; }")
        fold = ConstantFolding()
        prog, _ = fold.run(prog)
        val = _first_let_value(_first_func(prog))
        assert isinstance(val, A.BooleanLiteral)
        assert val.value is True

    def test_bool_equality(self):
        prog = _parse("fn main() -> int { let x: bool = true == false; return 0; }")
        fold = ConstantFolding()
        prog, _ = fold.run(prog)
        val = _first_let_value(_first_func(prog))
        assert isinstance(val, A.BooleanLiteral)
        assert val.value is False

    def test_non_constant_not_folded(self):
        """Expressions with variables should not be folded."""
        prog = _parse("fn main() -> int { let a: int = 5; let b: int = a + 3; return b; }")
        fold = ConstantFolding()
        prog, stats = fold.run(prog)
        func = _first_func(prog)
        # The second let (b = a + 3) should still be InfixExpression
        let_b = func.body.statements[1]
        assert isinstance(let_b, A.LetStatement)
        assert isinstance(let_b.value, A.InfixExpression)

    def test_call_args_folded(self):
        """Constants inside call arguments should be folded."""
        prog = _parse('fn foo(x: int) -> int { return x; } fn main() -> int { return foo(2 + 3); }')
        fold = ConstantFolding()
        prog, stats = fold.run(prog)
        # Find the call expression in main's return
        main_fn = prog.statements[1]
        ret_val = main_fn.body.statements[0].return_value
        assert isinstance(ret_val, A.CallExpression)
        assert isinstance(ret_val.arguments[0], A.IntegerLiteral)
        assert ret_val.arguments[0].value == 5

    def test_stats_count(self):
        prog = _parse("fn main() -> int { let x: int = 1 + 2 + 3; return x; }")
        fold = ConstantFolding()
        _, stats = fold.run(prog)
        assert stats.constants_folded >= 2


# ===========================================================================
# Dead Code Elimination
# ===========================================================================
class TestDeadCodeElimination:

    def test_stmts_after_return_removed(self):
        src = """
        fn main() -> int {
            return 0;
            let x: int = 5;
            let y: int = 10;
        }
        """
        prog = _parse(src)
        dce = DeadCodeElimination()
        prog, stats = dce.run(prog)
        func = _first_func(prog)
        assert len(func.body.statements) == 1  # only the return
        assert stats.dead_stmts_removed >= 2

    def test_stmts_after_break_removed(self):
        src = """
        fn main() -> int {
            while (true) {
                break;
                let x: int = 5;
            }
            return 0;
        }
        """
        prog = _parse(src)
        dce = DeadCodeElimination()
        prog, stats = dce.run(prog)
        func = _first_func(prog)
        while_stmt = func.body.statements[0]
        assert isinstance(while_stmt, A.WhileStatement)
        assert len(while_stmt.body.statements) == 1  # only the break
        assert stats.dead_stmts_removed >= 1

    def test_stmts_after_continue_removed(self):
        src = """
        fn main() -> int {
            while (true) {
                continue;
                let x: int = 5;
            }
            return 0;
        }
        """
        prog = _parse(src)
        dce = DeadCodeElimination()
        prog, stats = dce.run(prog)
        func = _first_func(prog)
        while_stmt = func.body.statements[0]
        assert len(while_stmt.body.statements) == 1

    def test_if_true_reduced_to_consequence(self):
        src = """
        fn main() -> int {
            if (true) {
                let x: int = 1;
            }
            return 0;
        }
        """
        prog = _parse(src)
        dce = DeadCodeElimination()
        prog, stats = dce.run(prog)
        func = _first_func(prog)
        # The if(true) should be replaced by its consequence block
        first_stmt = func.body.statements[0]
        assert isinstance(first_stmt, A.BlockStatement)
        assert stats.dead_stmts_removed >= 1

    def test_if_false_no_else_removed(self):
        src = """
        fn main() -> int {
            if (false) {
                let x: int = 1;
            }
            return 0;
        }
        """
        prog = _parse(src)
        dce = DeadCodeElimination()
        prog, stats = dce.run(prog)
        func = _first_func(prog)
        # Only the return should remain
        assert len(func.body.statements) == 1
        assert isinstance(func.body.statements[0], A.ReturnStatement)

    def test_if_false_with_else_reduced(self):
        src = """
        fn main() -> int {
            if (false) {
                let x: int = 1;
            } else {
                let y: int = 2;
            }
            return 0;
        }
        """
        prog = _parse(src)
        dce = DeadCodeElimination()
        prog, stats = dce.run(prog)
        func = _first_func(prog)
        # First statement should be the else block
        first_stmt = func.body.statements[0]
        assert isinstance(first_stmt, A.BlockStatement)

    def test_while_false_removed(self):
        src = """
        fn main() -> int {
            while (false) {
                let x: int = 1;
            }
            return 0;
        }
        """
        prog = _parse(src)
        dce = DeadCodeElimination()
        prog, stats = dce.run(prog)
        func = _first_func(prog)
        assert len(func.body.statements) == 1
        assert isinstance(func.body.statements[0], A.ReturnStatement)

    def test_non_constant_if_preserved(self):
        src = """
        fn main() -> int {
            let x: bool = true;
            if (x) {
                return 1;
            }
            return 0;
        }
        """
        prog = _parse(src)
        dce = DeadCodeElimination()
        prog, _ = dce.run(prog)
        func = _first_func(prog)
        # if statement should be preserved (condition is identifer, not literal)
        assert any(isinstance(s, A.IfStatement) for s in func.body.statements)


# ===========================================================================
# Constant Propagation
# ===========================================================================
class TestConstantPropagation:

    def test_simple_propagation(self):
        src = """
        fn main() -> int {
            let x: int = 42;
            return x;
        }
        """
        prog = _parse(src)
        prop = ConstantPropagation()
        prog, stats = prop.run(prog)
        ret = _return_value(_first_func(prog))
        assert isinstance(ret, A.IntegerLiteral)
        assert ret.value == 42
        assert stats.constants_propagated >= 1

    def test_mutated_variable_not_propagated(self):
        src = """
        fn main() -> int {
            let x: int = 42;
            x = 10;
            return x;
        }
        """
        prog = _parse(src)
        prop = ConstantPropagation()
        prog, stats = prop.run(prog)
        ret = _return_value(_first_func(prog))
        # x is mutated → should remain as identifier
        assert isinstance(ret, A.IdentifierLiteral)

    def test_postfix_marks_mutation(self):
        src = """
        fn main() -> int {
            let x: int = 5;
            x++;
            return x;
        }
        """
        prog = _parse(src)
        prop = ConstantPropagation()
        prog, stats = prop.run(prog)
        ret = _return_value(_first_func(prog))
        assert isinstance(ret, A.IdentifierLiteral)

    def test_loop_var_not_propagated(self):
        src = """
        fn main() -> int {
            for (let i: int = 0; i < 10; i++) {
                let unused: int = 0;
            }
            return 0;
        }
        """
        prog = _parse(src)
        prop = ConstantPropagation()
        prog, stats = prop.run(prog)
        # i is a for-loop variable, should be marked as mutated

    def test_propagation_in_expression(self):
        src = """
        fn main() -> int {
            let a: int = 10;
            let b: int = a + 5;
            return b;
        }
        """
        prog = _parse(src)
        prop = ConstantPropagation()
        prog, stats = prop.run(prog)
        func = _first_func(prog)
        # b = a + 5 should become b = 10 + 5
        let_b = func.body.statements[1]
        assert isinstance(let_b, A.LetStatement)
        infix = let_b.value
        assert isinstance(infix, A.InfixExpression)
        assert isinstance(infix.left_node, A.IntegerLiteral)
        assert infix.left_node.value == 10

    def test_propagation_does_not_cross_functions(self):
        """Constants defined in one function should not leak to another."""
        src = """
        fn foo() -> int {
            let x: int = 99;
            return x;
        }
        fn bar() -> int {
            let x: int = 1;
            return x;
        }
        fn main() -> int { return 0; }
        """
        prog = _parse(src)
        prop = ConstantPropagation()
        prog, stats = prop.run(prog)
        # foo's return should be 99, bar's should be 1
        foo = prog.statements[0]
        bar = prog.statements[1]
        foo_ret = _return_value(foo)
        bar_ret = _return_value(bar)
        assert isinstance(foo_ret, A.IntegerLiteral) and foo_ret.value == 99
        assert isinstance(bar_ret, A.IntegerLiteral) and bar_ret.value == 1

    def test_bool_propagation(self):
        src = """
        fn main() -> int {
            let flag: bool = true;
            if (flag) {
                return 1;
            }
            return 0;
        }
        """
        prog = _parse(src)
        prop = ConstantPropagation()
        prog, stats = prop.run(prog)
        func = _first_func(prog)
        if_stmt = func.body.statements[1]
        assert isinstance(if_stmt, A.IfStatement)
        # condition should now be BooleanLiteral(true)
        assert isinstance(if_stmt.condition, A.BooleanLiteral)
        assert if_stmt.condition.value is True


# ===========================================================================
# ASTOptimizer (orchestrator)
# ===========================================================================
class TestASTOptimizer:

    def test_opt_level_0_no_changes(self):
        src = "fn main() -> int { let x: int = 2 + 3; return x; }"
        prog = _parse(src)
        optimizer = ASTOptimizer(opt_level=0)
        prog, stats = optimizer.optimize(prog)
        # No folding at O0
        val = _first_let_value(_first_func(prog))
        assert isinstance(val, A.InfixExpression)
        assert stats.total == 0

    def test_opt_level_1_folds_constants(self):
        src = "fn main() -> int { let x: int = 2 + 3; return x; }"
        prog = _parse(src)
        optimizer = ASTOptimizer(opt_level=1)
        prog, stats = optimizer.optimize(prog)
        val = _first_let_value(_first_func(prog))
        assert isinstance(val, A.IntegerLiteral)
        assert val.value == 5

    def test_opt_level_2_folds_and_dce(self):
        src = """
        fn main() -> int {
            if (false) {
                let dead: int = 1;
            }
            let x: int = 2 + 3;
            return x;
        }
        """
        prog = _parse(src)
        optimizer = ASTOptimizer(opt_level=2)
        prog, stats = optimizer.optimize(prog)
        func = _first_func(prog)
        # if(false) should be eliminated; 2+3 folded
        assert stats.constants_folded >= 1
        assert stats.dead_stmts_removed >= 1
        # No IfStatement should remain
        assert not any(isinstance(s, A.IfStatement) for s in func.body.statements)

    def test_opt_level_3_propagates_and_folds(self):
        """O3: constant propagation → folding → DCE, iterated."""
        src = """
        fn main() -> int {
            let a: int = 10;
            let b: int = a + 5;
            return b;
        }
        """
        prog = _parse(src)
        optimizer = ASTOptimizer(opt_level=3)
        prog, stats = optimizer.optimize(prog)
        func = _first_func(prog)
        # After propagation: b = 10 + 5; after folding: b = 15
        let_b = func.body.statements[1]
        assert isinstance(let_b.value, A.IntegerLiteral)
        assert let_b.value.value == 15
        # return b → after propagation: return 15
        ret = func.body.statements[2]
        assert isinstance(ret, A.ReturnStatement)
        assert isinstance(ret.return_value, A.IntegerLiteral)
        assert ret.return_value.value == 15

    def test_opt_level_clamped(self):
        """Levels above 3 or below 0 are clamped."""
        opt = ASTOptimizer(opt_level=99)
        assert opt.opt_level == 3
        opt2 = ASTOptimizer(opt_level=-5)
        assert opt2.opt_level == 0

    def test_stats_object(self):
        stats = OptStats(constants_folded=3, dead_stmts_removed=2, constants_propagated=1)
        assert stats.total == 6
        assert "folded 3" in str(stats)
        assert "removed 2" in str(stats)
        assert "propagated 1" in str(stats)

    def test_empty_stats_string(self):
        stats = OptStats()
        assert str(stats) == "no optimizations applied"


# ===========================================================================
# LLVM optimization pass integration
# ===========================================================================
@pytest.mark.integration
class TestLLVMOptimization:

    def _compile_and_run(self, src: str, opt_level: int = 0) -> int:
        from util.executor import execute_module
        prog = _parse_and_sema(src)
        codegen = Codegen()
        module = codegen.compile(prog)
        assert not codegen.errors
        return execute_module(module, opt_level=opt_level)

    def test_run_with_o0(self):
        src = "fn main() -> int { return 42; }"
        assert self._compile_and_run(src, opt_level=0) == 42

    def test_run_with_o1(self):
        src = "fn main() -> int { return 42; }"
        assert self._compile_and_run(src, opt_level=1) == 42

    def test_run_with_o2(self):
        src = "fn main() -> int { return 42; }"
        assert self._compile_and_run(src, opt_level=2) == 42

    def test_run_with_o3(self):
        src = "fn main() -> int { return 42; }"
        assert self._compile_and_run(src, opt_level=3) == 42

    def test_arithmetic_optimized(self):
        """Optimizer should handle constant arithmetic and still produce correct result."""
        src = """
        fn main() -> int {
            let a: int = 10;
            let b: int = a + 20;
            let c: int = b * 2;
            return c;
        }
        """
        assert self._compile_and_run(src, opt_level=0) == 60
        assert self._compile_and_run(src, opt_level=2) == 60

    def test_loop_optimized(self):
        """Loops should work correctly with LLVM optimizations enabled."""
        src = """
        fn main() -> int {
            let sum: int = 0;
            for (let i: int = 0; i < 5; i++) {
                sum += i;
            }
            return sum;
        }
        """
        assert self._compile_and_run(src, opt_level=0) == 10
        assert self._compile_and_run(src, opt_level=2) == 10

    def test_combined_ast_and_llvm_opt(self):
        """Full pipeline: AST opt + LLVM opt should produce correct results."""
        src = """
        fn main() -> int {
            let x: int = 2 + 3;
            let y: int = x * 2;
            return y;
        }
        """
        prog = _parse_and_sema(src)
        # AST optimize
        optimizer = ASTOptimizer(opt_level=2)
        prog, ast_stats = optimizer.optimize(prog)
        # x should be folded to 5
        assert ast_stats.constants_folded >= 1
        # Codegen + LLVM opt + execute
        codegen = Codegen()
        module = codegen.compile(prog)
        assert not codegen.errors
        from util.executor import execute_module
        result = execute_module(module, opt_level=2)
        assert result == 10
