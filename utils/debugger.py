from pipeline.lexer import Lexer
from pipeline.parser import Parser
import json
from llvmlite import ir

def debug_lexer(code: str) -> None:
    """
    Debugs the lexer by printing tokens for the given source code.
    """
    print('===== LEXER DEBUG =====')
    lexer = Lexer(source=code)
    while lexer.current_char is not None:
        print(lexer.next_token())

def debug_parser(parser: Parser, program) -> None:
    """
    Debugs the parser by dumping the AST to a JSON file.
    """
    print('===== PARSER DEBUG =====')
    path = 'debug/ast.json'
    with open(path, 'w') as f:
        json.dump(program.json(), f, indent=4)
    print(f'Wrote AST to `{path}` successfully.')

def debug_compiler(module: ir.Module) -> None:
    """
    Debugs the compilation_unit by writing the LLVM IR to a file.
    """
    print('===== COMPILER DEBUG =====')
    path = 'debug/ir.ll'
    with open(path, 'w') as f:
        f.write(str(module))
    print(f'Wrote IR to `{path}` successfully.')
