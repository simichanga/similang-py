"""
Tests for array and struct support in Similang.

Covers:
- Lexer: new tokens (LBRACKET, RBRACKET, DOT, STRUCT)
- Parser: struct definitions, array literals, index expressions, field access,
          struct literals, array type annotations, index/field assignments
- Sema: type checking for arrays and structs
- Codegen: IR generation for arrays and structs
"""
import pytest
from frontend.lexer import Lexer
from frontend.parser import Parser
from frontend.token import TokenType
from frontend import ast as A
from middle.sema import SemanticAnalyzer
from middle.types import TypeSystem
from backend.codegen import Codegen


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _lex_all(src: str) -> list:
    """Return all tokens (excluding EOF)."""
    lex = Lexer(src)
    tokens = []
    while True:
        tok = lex.next_token()
        if tok.type == TokenType.EOF:
            break
        tokens.append(tok)
    return tokens


def _parse(src: str) -> A.Program:
    lex = Lexer(src)
    p = Parser(lex)
    prog = p.parse_program()
    assert not p.error_collector.has_errors(), \
        f"Parser errors: {[e.format() for e in p.error_collector.errors]}"
    return prog


def _parse_errors(src: str) -> list:
    lex = Lexer(src)
    p = Parser(lex)
    p.parse_program()
    return [e.format() for e in p.error_collector.errors]


def _analyze(src: str):
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


def _compile(src: str):
    """Parse + analyze + codegen; return module IR string."""
    lex = Lexer(src)
    p = Parser(lex)
    prog = p.parse_program()
    assert not p.error_collector.has_errors(), \
        f"Parser errors: {[e.format() for e in p.error_collector.errors]}"
    sema = SemanticAnalyzer()
    ok, errors = sema.analyze(prog)
    assert ok, f"Sema errors: {errors}"
    cg = Codegen()
    # Register struct types in codegen's type system
    for stmt in prog.statements:
        if isinstance(stmt, A.StructDefinition):
            struct_name = stmt.name.value
            fields = {}
            for f in stmt.fields:
                fields[f.name] = cg.types.resolve_alias(f.value_type)
            if not cg.types.is_struct_type(struct_name):
                cg.types.create_struct_type(struct_name, fields)
    module = cg.compile(prog)
    assert not cg.errors, f"Codegen errors: {cg.errors}"
    return str(module)


# ===========================================================================
# Lexer tests
# ===========================================================================
class TestLexerNewTokens:
    def test_brackets(self):
        tokens = _lex_all("[1, 2]")
        types = [t.type for t in tokens]
        assert TokenType.LBRACKET in types
        assert TokenType.RBRACKET in types

    def test_dot(self):
        tokens = _lex_all("a.b")
        types = [t.type for t in tokens]
        assert TokenType.DOT in types

    def test_struct_keyword(self):
        tokens = _lex_all("struct Foo {}")
        assert tokens[0].type == TokenType.STRUCT
        assert tokens[0].literal == "struct"

    def test_mixed_tokens(self):
        tokens = _lex_all("let x: [3]int = [1, 2, 3];")
        types = [t.type for t in tokens]
        assert TokenType.LBRACKET in types
        assert TokenType.RBRACKET in types


# ===========================================================================
# Parser tests — arrays
# ===========================================================================
class TestParserArrays:
    def test_array_literal(self):
        prog = _parse("fn main() -> int { let x: [3]int = [1, 2, 3]; return 0; }")
        fn = prog.statements[0]
        let_stmt = fn.body.statements[0]
        assert isinstance(let_stmt, A.LetStatement)
        assert let_stmt.value_type == "[3]int"
        assert isinstance(let_stmt.value, A.ArrayLiteral)
        assert len(let_stmt.value.elements) == 3

    def test_array_type_annotation(self):
        prog = _parse("fn main() -> int { let nums: [5]float = [1.0, 2.0, 3.0, 4.0, 5.0]; return 0; }")
        let_stmt = prog.statements[0].body.statements[0]
        assert let_stmt.value_type == "[5]float"

    def test_array_index_expression(self):
        prog = _parse("fn main() -> int { let a: [3]int = [10, 20, 30]; let x: int = a[1]; return 0; }")
        fn = prog.statements[0]
        # Second statement is let x = a[1]
        let_x = fn.body.statements[1]
        assert isinstance(let_x, A.LetStatement)
        assert isinstance(let_x.value, A.IndexExpression)
        assert isinstance(let_x.value.left, A.IdentifierLiteral)
        assert let_x.value.left.value == "a"

    def test_array_index_assign(self):
        prog = _parse("fn main() -> int { let a: [3]int = [1, 2, 3]; a[0] = 42; return 0; }")
        fn = prog.statements[0]
        assign = fn.body.statements[1]
        assert isinstance(assign, A.IndexAssignStatement)


# ===========================================================================
# Parser tests — structs
# ===========================================================================
class TestParserStructs:
    def test_struct_definition(self):
        prog = _parse("struct Point { x: int, y: int }")
        assert len(prog.statements) == 1
        sd = prog.statements[0]
        assert isinstance(sd, A.StructDefinition)
        assert sd.name.value == "Point"
        assert len(sd.fields) == 2
        assert sd.fields[0].name == "x"
        assert sd.fields[0].value_type == "int"
        assert sd.fields[1].name == "y"
        assert sd.fields[1].value_type == "int"

    def test_struct_definition_trailing_comma(self):
        prog = _parse("struct Vec3 { x: float, y: float, z: float, }")
        sd = prog.statements[0]
        assert len(sd.fields) == 3

    def test_struct_literal(self):
        src = """
        struct Point { x: int, y: int }
        fn main() -> int {
            let p: Point = Point { x: 10, y: 20 };
            return 0;
        }
        """
        prog = _parse(src)
        fn = prog.statements[1]
        let_stmt = fn.body.statements[0]
        assert isinstance(let_stmt, A.LetStatement)
        assert isinstance(let_stmt.value, A.StructLiteral)
        assert let_stmt.value.struct_name == "Point"
        assert len(let_stmt.value.field_values) == 2

    def test_field_access(self):
        src = """
        struct Point { x: int, y: int }
        fn main() -> int {
            let p: Point = Point { x: 10, y: 20 };
            let px: int = p.x;
            return 0;
        }
        """
        prog = _parse(src)
        fn = prog.statements[1]
        let_px = fn.body.statements[1]
        assert isinstance(let_px.value, A.FieldAccessExpression)
        assert let_px.value.field_name == "x"

    def test_field_assign(self):
        src = """
        struct Point { x: int, y: int }
        fn main() -> int {
            let p: Point = Point { x: 10, y: 20 };
            p.x = 42;
            return 0;
        }
        """
        prog = _parse(src)
        fn = prog.statements[1]
        assign = fn.body.statements[1]
        assert isinstance(assign, A.FieldAssignStatement)
        assert assign.field_name == "x"


# ===========================================================================
# Sema tests — arrays
# ===========================================================================
class TestSemaArrays:
    def test_valid_array_let(self):
        _ok("fn main() -> int { let a: [3]int = [1, 2, 3]; return 0; }")

    def test_valid_array_float(self):
        _ok("fn main() -> int { let a: [2]float = [1.0, 2.0]; return 0; }")

    def test_array_element_type_mismatch(self):
        _fails("fn main() -> int { let a: [2]int = [1, 2.5]; return 0; }",
               match="element type mismatch")

    def test_array_size_type_mismatch(self):
        _fails("fn main() -> int { let a: [3]int = [1, 2]; return 0; }",
               match="cannot assign")

    def test_array_index_type_check(self):
        _ok("fn main() -> int { let a: [3]int = [1, 2, 3]; let x: int = a[0]; return 0; }")

    def test_index_non_array_fails(self):
        _fails("fn main() -> int { let x: int = 5; let y: int = x[0]; return 0; }",
               match="non-array")

    def test_index_float_fails(self):
        _fails("fn main() -> int { let a: [3]int = [1, 2, 3]; let x: int = a[1.0]; return 0; }",
               match="must be integer")

    def test_array_index_assign_type_check(self):
        _ok("""
        fn main() -> int {
            let a: [3]int = [1, 2, 3];
            a[0] = 42;
            return 0;
        }
        """)


# ===========================================================================
# Sema tests — structs
# ===========================================================================
class TestSemaStructs:
    def test_valid_struct_definition(self):
        _ok("""
        struct Point { x: int, y: int }
        fn main() -> int {
            let p: Point = Point { x: 10, y: 20 };
            return 0;
        }
        """)

    def test_unknown_struct_type(self):
        _fails("fn main() -> int { let p: Foo = Foo { x: 1 }; return 0; }",
               match="Unknown")

    def test_missing_field(self):
        _fails("""
        struct Point { x: int, y: int }
        fn main() -> int {
            let p: Point = Point { x: 10 };
            return 0;
        }
        """, match="Missing field")

    def test_unknown_field(self):
        _fails("""
        struct Point { x: int, y: int }
        fn main() -> int {
            let p: Point = Point { x: 10, y: 20, z: 30 };
            return 0;
        }
        """, match="Unknown field")

    def test_field_type_mismatch(self):
        _fails("""
        struct Point { x: int, y: int }
        fn main() -> int {
            let p: Point = Point { x: 10, y: true };
            return 0;
        }
        """, match="Type mismatch")

    def test_field_access_type_check(self):
        _ok("""
        struct Point { x: int, y: int }
        fn main() -> int {
            let p: Point = Point { x: 10, y: 20 };
            let px: int = p.x;
            return px;
        }
        """)

    def test_field_access_unknown_field(self):
        _fails("""
        struct Point { x: int, y: int }
        fn main() -> int {
            let p: Point = Point { x: 10, y: 20 };
            let pz: int = p.z;
            return 0;
        }
        """, match="no field")

    def test_field_assign_type_check(self):
        _ok("""
        struct Point { x: int, y: int }
        fn main() -> int {
            let p: Point = Point { x: 10, y: 20 };
            p.x = 42;
            return 0;
        }
        """)

    def test_field_access_on_non_struct(self):
        _fails("fn main() -> int { let x: int = 5; let y: int = x.z; return 0; }",
               match="non-struct")

    def test_duplicate_field_in_literal(self):
        _fails("""
        struct Point { x: int, y: int }
        fn main() -> int {
            let p: Point = Point { x: 10, x: 20 };
            return 0;
        }
        """, match="Duplicate field")


# ===========================================================================
# Codegen tests — arrays
# ===========================================================================
class TestCodegenArrays:
    def test_array_codegen(self):
        ir_str = _compile("""
        fn main() -> int {
            let a: [3]int = [10, 20, 30];
            let x: int = a[1];
            return x;
        }
        """)
        assert "alloca" in ir_str
        assert "getelementptr" in ir_str

    def test_array_index_assign_codegen(self):
        ir_str = _compile("""
        fn main() -> int {
            let a: [3]int = [1, 2, 3];
            a[0] = 42;
            return a[0];
        }
        """)
        assert "store" in ir_str
        assert "getelementptr" in ir_str


# ===========================================================================
# Codegen tests — structs
# ===========================================================================
class TestCodegenStructs:
    def test_struct_codegen(self):
        ir_str = _compile("""
        struct Point { x: int, y: int }
        fn main() -> int {
            let p: Point = Point { x: 10, y: 20 };
            let px: int = p.x;
            return px;
        }
        """)
        assert "getelementptr" in ir_str

    def test_struct_field_assign_codegen(self):
        ir_str = _compile("""
        struct Point { x: int, y: int }
        fn main() -> int {
            let p: Point = Point { x: 10, y: 20 };
            p.x = 42;
            return p.x;
        }
        """)
        assert "store" in ir_str
        assert "getelementptr" in ir_str


# ===========================================================================
# Type system tests
# ===========================================================================
class TestTypeSystem:
    def test_array_type_creation(self):
        ts = TypeSystem()
        arr = ts.get_array_type("int", 5)
        assert arr.name == "[5]int"
        assert arr.element_type.name == "int"
        assert arr.size == 20

    def test_struct_type_creation(self):
        ts = TypeSystem()
        st = ts.create_struct_type("Point", {"x": "int", "y": "int"})
        assert st.name == "Point"
        assert "x" in st.fields
        assert "y" in st.fields
        assert ts.is_struct_type("Point")

    def test_is_array_type(self):
        ts = TypeSystem()
        assert ts.is_array_type("[3]int")
        assert ts.is_array_type("[10]float")
        assert not ts.is_array_type("int")
        assert not ts.is_array_type("Point")

    def test_array_element_type(self):
        ts = TypeSystem()
        assert ts.array_element_type("[3]int") == "int"
        assert ts.array_element_type("[5]float") == "float"

    def test_struct_field_index(self):
        ts = TypeSystem()
        ts.create_struct_type("Point", {"x": "int", "y": "int"})
        assert ts.get_struct_field_index("Point", "x") == 0
        assert ts.get_struct_field_index("Point", "y") == 1
        assert ts.get_struct_field_index("Point", "z") is None

    def test_struct_field_type(self):
        ts = TypeSystem()
        ts.create_struct_type("Point", {"x": "int", "y": "float"})
        assert ts.get_struct_field_type("Point", "x") == "int"
        assert ts.get_struct_field_type("Point", "y") == "float"

    def test_array_type_exists(self):
        ts = TypeSystem()
        assert ts.exists("[3]int")
        assert ts.exists("[10]float")
        assert not ts.exists("[3]mystery")

    def test_can_assign_arrays(self):
        ts = TypeSystem()
        assert ts.can_assign("[3]int", "[3]int")
        assert not ts.can_assign("[3]int", "[4]int")
        assert not ts.can_assign("[3]int", "[3]float")

    def test_can_assign_structs(self):
        ts = TypeSystem()
        ts.create_struct_type("A", {"x": "int"})
        ts.create_struct_type("B", {"x": "int"})
        assert ts.can_assign("A", "A")
        assert not ts.can_assign("A", "B")
