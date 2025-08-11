from frontend.lexer import Lexer
from frontend.parser import Parser
from frontend.ast import Program, FunctionStatement, LetStatement

def test_parser_function_and_let():
    src = 'let a: int = 5; fn main() -> int { return a; }'
    lex = Lexer(src)
    p = Parser(lex)
    program = p.parse_program()
    assert isinstance(program, Program)
    # expecting two top-level statements: let, function
    assert len(program.statements) == 2
    assert isinstance(program.statements[0], LetStatement)
    assert isinstance(program.statements[1], FunctionStatement)
    assert p.errors == []
