from core_pipeline.lexer import Lexer
from core_pipeline.parser import Parser
from core_pipeline.compiler import Compiler
from core_pipeline.ast import Program

from pipeline.lexer_debugger import debug_lexer
from pipeline.parser_debugger import debug_parser
from pipeline.compiler_debugger import debug_compiler
from pipeline.executor import execute_code

from utils.config import Config

import logging
import time
import argparse

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

# Configure benchmarking
def benchmark_stage(stage_name, func, *args, **kwargs) -> any:
    """Benchmark a specific stage of the compiler."""
    if Config.SHOW_BENCHMARK:
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"{stage_name} took {elapsed_time:.4f} seconds")
    else:
        result = func(*args, **kwargs)
    return result

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Similang Compiler')
    parser.add_argument('--debug', action='store_true', help='Enable all debug outputs')
    parser.add_argument('--show-benchmark', action='store_true', help='Show benchmark outputs')
    parser.add_argument('--show-execution-output', action='store_true', help='Show execution output')
    return parser.parse_args()

def configure_debug_settings(args):
    """Configure debug settings based on command line arguments."""
    if args.debug:
        Config.enable_all_debug()
    if args.show_benchmark:
        Config.SHOW_BENCHMARK = True
    if args.show_execution_output:
        Config.SHOW_EXECUTION_OUTPUT = True

def compile_and_execute(code):
    """Compile and execute the code."""
    lexer: Lexer = benchmark_stage("Lexer", Lexer, source=code)
    parser: Parser = benchmark_stage("Parser", Parser, lexer=lexer)

    if parser.errors:
        for error in parser.errors:
            logger.error(error)
        exit(1)

    if Config.LEXER_DEBUG:
        debug_lexer(code)

    ast: Program = benchmark_stage("AST", parser.parse_program)

    if Config.PARSER_DEBUG:
        debug_parser(parser, ast)

    compiler: Compiler = benchmark_stage("Compiler", Compiler)
    benchmark_stage("Compilation", compiler.compile, node=ast)
    module = compiler.module

    if Config.COMPILER_DEBUG:
        debug_compiler(module)

    if Config.RUN_CODE:
        benchmark_stage("Execution", execute_code, module)

def main():
    args = parse_arguments()

    configure_debug_settings(args)

    code = load_code('tests/test.simi')

    compile_and_execute(code)

if __name__ == '__main__':
    main()
