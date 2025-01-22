from Lexer import Lexer
from Parser import Parser
from Compiler import Compiler
from AST import Program
import json
import time

from llvmlite import ir
import llvmlite.binding as llvm
from ctypes import CFUNCTYPE, c_int, c_float

LEXER_DEBUG: bool = False
PARSER_DEBUG: bool = False
COMPILER_DEBUG: bool = False
RUN_CODE: bool = True

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

        debug_lex: Lexer = Lexer(source = code)

        while debug_lex.current_char is not None:
            print(debug_lex.next_token())

    program: Program = p.parse_program()
    
    if PARSER_DEBUG:
        print('===== PARSER DEBUG =====')    
        
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

    if RUN_CODE:
        llvm.initialize()
        llvm.initialize_native_target()
        llvm.initialize_native_asmprinter()

        try:
            llvm_ir_parsed = llvm.parse_assembly(str(module))
            llvm_ir_parsed.verify()
        except Exception as e:
            print(e)
            raise

        target_machine = llvm.Target.from_default_triple().create_target_machine()

        engine = llvm.create_mcjit_compiler(llvm_ir_parsed, target_machine)
        engine.finalize_object()

        entry = engine.get_function_address('main')
        cfunc = CFUNCTYPE(c_int)(entry)

        st = time.time()

        result = cfunc()

        et = time.time()

        print(f'\nProgram returned: {result}\n=== Executed in {round((et - st) * 1000, 6)} ms. ===')