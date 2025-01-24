from Lexer import Lexer
from Parser import Parser
from Compiler import Compiler
from AST import Program
from optimizer.Optimizer import Optimizer

from pipeline.lexer_debugger import debug_lexer
from pipeline.parser_debugger import debug_parser
from pipeline.compiler_debugger import debug_compiler
from pipeline.executor import execute_code

from utils.config import Config

if __name__ == '__main__':
    with open('tests/test.simi', 'r') as f:
        code = f.read()

    lexer = Lexer(source=code)
    parser = Parser(lexer=lexer)

    if len(parser.errors) > 0:
        print(err for err in parser.errors)
        exit(1)

    if Config.LEXER_DEBUG:
        debug_lexer(code)

    ast: Program = parser.parse_program()

    ast: Optimizer = Optimizer.optimize(ast)

    if Config.PARSER_DEBUG:
        debug_parser(parser, ast)

    compiler: Compiler = Compiler()
    compiler.compile(node = ast)
    module = compiler.module

    if Config.COMPILER_DEBUG:
        debug_compiler(module)

    if Config.RUN_CODE:
        execute_code(module)
