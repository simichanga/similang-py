"""
Thorough unit tests for the Similang parser.
"""
import pytest
from frontend.lexer import Lexer
from frontend.parser import Parser
from frontend import ast as A


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _parse(src: str) -> A.Program:
    """Parse *src* and return the AST program node."""
    lex = Lexer(src)
    p = Parser(lex)
    prog = p.parse_program()
    assert not p.error_collector.has_errors(), \
        f"Parser errors: {[e.format() for e in p.error_collector.errors]}"
    return prog


def _parse_with_errors(src: str):
    """Parse *src* and return (program, error_collector)."""
    lex = Lexer(src)
    p = Parser(lex)
    prog = p.parse_program()
    return prog, p.error_collector


# ---------------------------------------------------------------------------
# Let statements
# ---------------------------------------------------------------------------
class TestLetStatement:
    def test_basic_let(self):
        prog = _parse("let x: int = 5;")
        assert len(prog.statements) == 1
        stmt = prog.statements[0]
        assert isinstance(stmt, A.LetStatement)
        assert stmt.name.value == "x"
        assert stmt.value_type == "int"
        assert isinstance(stmt.value, A.IntegerLiteral)
        assert stmt.value.value == 5

    def test_let_float(self):
        prog = _parse("let pi: float = 3.14;")
        stmt = prog.statements[0]
        assert isinstance(stmt, A.LetStatement)
        assert stmt.value_type == "float"
        assert isinstance(stmt.value, A.FloatLiteral)

    def test_let_bool(self):
        prog = _parse("let flag: bool = true;")
        stmt = prog.statements[0]
        assert stmt.value_type == "bool"
        assert isinstance(stmt.value, A.BooleanLiteral)
        assert stmt.value.value is True

    def test_let_string(self):
        prog = _parse('let s: str = "hello";')
        stmt = prog.statements[0]
        assert stmt.value_type == "str"
        assert isinstance(stmt.value, A.StringLiteral)
        assert stmt.value.value == "hello"

    @pytest.mark.parametrize("alias,canonical_type", [
        ("i32", "i32"),
        ("f32", "f32"),
        ("string", "string"),
        ("i64", "i64"),
        ("u8", "u8"),
    ])
    def test_let_with_type_alias(self, alias, canonical_type):
        """Type aliases should be accepted in let statements."""
        prog = _parse(f"let x: {alias} = 0;")
        stmt = prog.statements[0]
        assert isinstance(stmt, A.LetStatement)
        assert stmt.value_type == canonical_type

    def test_let_with_expression(self):
        prog = _parse("let x: int = 1 + 2 * 3;")
        stmt = prog.statements[0]
        # The value should be an infix expression (1 + (2 * 3))
        assert isinstance(stmt.value, A.InfixExpression)


# ---------------------------------------------------------------------------
# Function statements
# ---------------------------------------------------------------------------
class TestFunctionStatement:
    def test_basic_function(self):
        prog = _parse("fn main() -> int { return 42; }")
        assert len(prog.statements) == 1
        fn = prog.statements[0]
        assert isinstance(fn, A.FunctionStatement)
        assert fn.name.value == "main"
        assert fn.return_type == "int"
        assert len(fn.parameters) == 0
        assert isinstance(fn.body, A.BlockStatement)

    def test_function_with_params(self):
        prog = _parse("fn add(a: int, b: int) -> int { return a + b; }")
        fn = prog.statements[0]
        assert len(fn.parameters) == 2
        assert fn.parameters[0].name == "a"
        assert fn.parameters[0].value_type == "int"
        assert fn.parameters[1].name == "b"
        assert fn.parameters[1].value_type == "int"

    def test_function_with_alias_types(self):
        prog = _parse("fn foo(x: i32) -> i32 { return x; }")
        fn = prog.statements[0]
        assert fn.parameters[0].value_type == "i32"
        assert fn.return_type == "i32"

    def test_void_function(self):
        prog = _parse("fn noop() -> void { }")
        fn = prog.statements[0]
        assert fn.return_type == "void"


# ---------------------------------------------------------------------------
# Expressions
# ---------------------------------------------------------------------------
class TestExpressions:
    def test_integer_expression(self):
        prog = _parse("42;")
        stmt = prog.statements[0]
        assert isinstance(stmt, A.ExpressionStatement)
        assert isinstance(stmt.expr, A.IntegerLiteral)
        assert stmt.expr.value == 42

    def test_infix_addition(self):
        prog = _parse("1 + 2;")
        stmt = prog.statements[0]
        assert isinstance(stmt.expr, A.InfixExpression)
        assert stmt.expr.operator == "+"

    def test_infix_precedence(self):
        """Multiplication binds tighter than addition."""
        prog = _parse("1 + 2 * 3;")
        expr = prog.statements[0].expr
        # Should parse as (1 + (2 * 3))
        assert isinstance(expr, A.InfixExpression)
        assert expr.operator == "+"
        assert isinstance(expr.right_node, A.InfixExpression)
        assert expr.right_node.operator == "*"

    def test_grouped_expression(self):
        prog = _parse("(1 + 2) * 3;")
        expr = prog.statements[0].expr
        assert isinstance(expr, A.InfixExpression)
        assert expr.operator == "*"
        assert isinstance(expr.left_node, A.InfixExpression)
        assert expr.left_node.operator == "+"

    def test_prefix_negation(self):
        prog = _parse("-5;")
        expr = prog.statements[0].expr
        assert isinstance(expr, A.PrefixExpression)
        assert expr.operator == "-"

    def test_prefix_not(self):
        prog = _parse("!true;")
        expr = prog.statements[0].expr
        assert isinstance(expr, A.PrefixExpression)
        assert expr.operator == "!"

    def test_postfix_increment(self):
        prog = _parse("x++;")
        expr = prog.statements[0].expr
        assert isinstance(expr, A.PostfixExpression)
        assert expr.operator == "++"

    def test_postfix_decrement(self):
        prog = _parse("x--;")
        expr = prog.statements[0].expr
        assert isinstance(expr, A.PostfixExpression)
        assert expr.operator == "--"

    @pytest.mark.parametrize("op", ["==", "!=", "<", ">", "<=", ">="])
    def test_comparison_operators(self, op):
        prog = _parse(f"1 {op} 2;")
        expr = prog.statements[0].expr
        assert isinstance(expr, A.InfixExpression)
        assert expr.operator == op


# ---------------------------------------------------------------------------
# Call expressions
# ---------------------------------------------------------------------------
class TestCallExpressions:
    def test_no_args(self):
        prog = _parse("foo();")
        expr = prog.statements[0].expr
        assert isinstance(expr, A.CallExpression)
        assert expr.function.value == "foo"
        assert len(expr.arguments) == 0

    def test_with_args(self):
        prog = _parse("add(1, 2);")
        expr = prog.statements[0].expr
        assert isinstance(expr, A.CallExpression)
        assert len(expr.arguments) == 2

    def test_nested_calls(self):
        prog = _parse("outer(inner(1));")
        expr = prog.statements[0].expr
        assert isinstance(expr, A.CallExpression)
        assert isinstance(expr.arguments[0], A.CallExpression)


# ---------------------------------------------------------------------------
# Control flow
# ---------------------------------------------------------------------------
class TestControlFlow:
    def test_if_statement(self):
        prog = _parse("if (true) { 1; }")
        stmt = prog.statements[0]
        assert isinstance(stmt, A.IfStatement)
        assert stmt.consequence is not None
        assert stmt.alternative is None

    def test_if_else_statement(self):
        prog = _parse("if (true) { 1; } else { 2; }")
        stmt = prog.statements[0]
        assert isinstance(stmt, A.IfStatement)
        assert stmt.consequence is not None
        assert stmt.alternative is not None

    def test_while_statement(self):
        prog = _parse("while true { 1; }")
        stmt = prog.statements[0]
        assert isinstance(stmt, A.WhileStatement)

    def test_for_statement(self):
        prog = _parse("for (let i: int = 0; i < 10; i++) { }")
        stmt = prog.statements[0]
        assert isinstance(stmt, A.ForStatement)
        assert stmt.var_declaration is not None

    def test_break_statement(self):
        prog = _parse("break;")
        stmt = prog.statements[0]
        assert isinstance(stmt, A.BreakStatement)

    def test_continue_statement(self):
        prog = _parse("continue;")
        stmt = prog.statements[0]
        assert isinstance(stmt, A.ContinueStatement)


# ---------------------------------------------------------------------------
# Assignment statements
# ---------------------------------------------------------------------------
class TestAssignment:
    def test_simple_assignment(self):
        prog = _parse("x = 5;")
        stmt = prog.statements[0]
        assert isinstance(stmt, A.AssignStatement)
        assert stmt.operator == "="

    @pytest.mark.parametrize("op", ["+=", "-=", "*=", "/="])
    def test_compound_assignment(self, op):
        prog = _parse(f"x {op} 1;")
        stmt = prog.statements[0]
        assert isinstance(stmt, A.AssignStatement)
        assert stmt.operator == op


# ---------------------------------------------------------------------------
# Return statements
# ---------------------------------------------------------------------------
class TestReturn:
    def test_return_expression(self):
        prog = _parse("fn f() -> int { return 42; }")
        fn = prog.statements[0]
        ret = fn.body.statements[0]
        assert isinstance(ret, A.ReturnStatement)
        assert isinstance(ret.return_value, A.IntegerLiteral)


# ---------------------------------------------------------------------------
# Multiple statements
# ---------------------------------------------------------------------------
class TestMultipleStatements:
    def test_let_and_function(self):
        src = "let a: int = 5; fn main() -> int { return a; }"
        prog = _parse(src)
        assert len(prog.statements) == 2
        assert isinstance(prog.statements[0], A.LetStatement)
        assert isinstance(prog.statements[1], A.FunctionStatement)


# ---------------------------------------------------------------------------
# AST JSON serialization
# ---------------------------------------------------------------------------
class TestASTJson:
    def test_program_json(self):
        prog = _parse("let x: int = 1;")
        j = prog.json()
        assert j["type"] == "Program"
        assert len(j["statements"]) == 1
        assert j["statements"][0]["type"] == "LetStatement"
