import pytest
from frontend.lexer import Lexer
from frontend.parser import Parser
from middle.sema import SemanticAnalyzer
from backend.codegen import Codegen
from util.executor import execute_module

@pytest.mark.integration
def test_codegen_exec_simple_program(tmp_path):
    src = '''
    fn main() -> int {
      let x: int = 40;
      let y: int = 2;
      return x + y;
    }'''
    lex = Lexer(src)
    p = Parser(lex)
    prog = p.parse_program()
    sema = SemanticAnalyzer()
    ok, errors = sema.analyze(prog)
    assert ok, f"sema errors: {errors}"
    cg = Codegen()
    module = cg.compile(prog)
    # basic sanity: IR contains define main
    assert 'define' in str(module)
    # execute (requires llvmlite and MCJIT)
    res = execute_module(module)
    assert res == 42
