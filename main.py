from Lexer import Lexer
from Parser import Parser
from Compiler import Compiler
from AST import Program
import json

from llvmlite import ir
import llvmlite.binding as llvm
from ctypes import CFUNCTYPE, c_int, c_float

LEXER_DEBUG: bool = True
PARSER_DEBUG: bool = True
COMPILER_DEBUG: bool = True

if __name__ == '__main__':
    with open('tests/test.simi', 'r') as f:
        code: str = f.read()
        
    l: Lexer = Lexer(source = code)
    p: Parser = Parser(lexer = l)

    if len(p.errors) > 0:
        print(err for err in p.errors)
        exit(1)

    if LEXER_DEBUG:
        print('===== LEXER DEBUG =====')

        with open('tests/test.simi', 'r') as f:
            code: str = f.read()

        debug_lex: Lexer = Lexer(source = code)

        while debug_lex.current_char is not None:
            print(debug_lex.next_token())

    if PARSER_DEBUG:
        print('===== PARSER DEBUG =====')

        program: Program = p.parse_program()
        
        PATH: str = 'debug/ast.json'
        with open(PATH, 'w') as f:
            json.dump(program.json(), f, indent = 4)
        
        print(f'Wrote AST to `{PATH}` successfully.')

    c: Compiler = Compiler()
    c.compile(node = program)

    # Output Steps
    module: ir.Module = c.module
    module.triple = llvm.get_default_triple()

    if COMPILER_DEBUG:
        print('===== COMPILER DEBUG =====')

        PATH: str = 'debug/ir.ll'
        with open('debug/ir.ll', 'w') as f:
            f.write(str(module))

        print(f'Wrote IR to `{PATH}` successfully.')