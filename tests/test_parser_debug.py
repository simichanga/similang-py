"""
Debug-dump integration test.  This test intentionally fails so that the
debug_dumper fixture writes AST / token dumps for manual inspection.
Skip in normal CI runs.
"""
import pytest
from frontend.lexer import Lexer
from frontend.parser import Parser


@pytest.mark.skip(reason="intentionally-failing debug test — run manually")
def test_parser_debug_example(debug_dumper):
    src = "fn main() -> int { let x: int = 1 + 2; return x; }"
    lexer = Lexer(src)
    parser = Parser(lexer)
    program = parser.parse_program()

    debug_dumper.register_ast(program, name="test_parser_debug_example")

    lexer2 = Lexer(src)
    debug_dumper.register_tokens(lexer2, name="test_parser_debug_example_tokens")

    # Intentional failure to trigger dump
    assert len(program.statements) == 999
