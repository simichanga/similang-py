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
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG if Config.DEBUG else logging.INFO)
logger = logging.getLogger(__name__)

def load_code(file_path: str) -> str:
    """Load code from a file."""
    try:
        with open(file_path, 'r') as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        exit(1)

def main():
    # Load code
    code = load_code('tests/test.simi')

    # Lexer
    lexer = Lexer(source=code)
    parser = Parser(lexer=lexer)

    if parser.errors:
        for error in parser.errors:
            logger.error(error)
        exit(1)

    if Config.LEXER_DEBUG:
        debug_lexer(code)

    # Parse program
    ast: Program = parser.parse_program()

    if Config.PARSER_DEBUG:
        debug_parser(parser, ast)

    # Compile
    compiler: Compiler = Compiler()
    compiler.compile(node=ast)
    module = compiler.module

    if Config.COMPILER_DEBUG:
        debug_compiler(module)

    # Execute
    if Config.RUN_CODE:
        execute_code(module)

if __name__ == '__main__':
    main()
