from frontend.lexer import Lexer
from frontend.parser import Parser
from middle.sema import SemanticAnalyzer

def test_sema_detects_undeclared_variable():
    src = 'fn main() -> int { return x; }'
    lex = Lexer(src)
    p = Parser(lex)
    program = p.parse_program()
    sema = SemanticAnalyzer()
    ok, errors = sema.analyze(program)
    assert not ok
    assert any('Undeclared identifier' in e for e in errors)
