import pytest

from frontend.lexer import Lexer
from frontend.parser import Parser

@pytest.mark.skip(reason="Temporarily skip debugging tests")
def test_parser_debug_example(debug_dumper):
    src = 'fn main() -> int { let x: int = 1 + 2; return x; }'
    lexer = Lexer(src)
    parser = Parser(lexer)
    program = parser.parse_program()

    # register an AST dump (will be executed if test fails)
    debug_dumper.register_ast(program, name="test_parser_debug_example")

    # also register a token dump; remember dump_tokens will exhaust the lexer,
    # so create a fresh lexer if you want both parse + token dump
    lexer2 = Lexer(src)
    debug_dumper.register_tokens(lexer2, name="test_parser_debug_example_tokens")

    # Cause an intentional failure to see dumps produced:
    assert len(program.statements) == 999  # will fail -> dumps will be written
