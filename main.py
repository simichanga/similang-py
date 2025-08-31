"""
Top-level driver for Similang (refactored layout).
Usage:
    python main.py path/to/file.simi [--no-run] [--debug] [--show-benchmark]

This script:
 - reads the source file
 - lexes and parses into AST
 - runs semantic analysis
 - generates LLVM IR
 - writes debug/ir.ll
 - optionally runs the compiled code using llvmlite (MCJIT)
"""
from __future__ import annotations
import argparse
import logging
import sys
from pathlib import Path

from frontend.lexer import Lexer
from frontend.parser import Parser
from middle.sema import SemanticAnalyzer
from backend.codegen import Codegen
from util.config import Config
from util.executor import execute_module
from util.debug import dump_ast, dump_tokens, dump_ir

logging.basicConfig(level=logging.DEBUG if Config.DEBUG else logging.INFO)
logger = logging.getLogger("similang")

def parse_args():
    p = argparse.ArgumentParser(description="Similang compiler driver")
    p.add_argument("file", help="Source file (.simi)")
    p.add_argument("--no-run", action="store_true", help="Do not execute the produced code")
    p.add_argument("--debug", action="store_true", help="Enable debug flags")
    p.add_argument("--show-benchmark", action="store_true", help="Show benchmark info")
    return p.parse_args()

def load_source(path: str) -> str:
    p = Path(path)
    if not p.exists():
        logger.error("Source file not found: %s", path)
        sys.exit(1)
    return p.read_text(encoding='utf8')

def main():
    args = parse_args()
    if args.debug:
        Config.enable_all_debug()
        logging.getLogger().setLevel(logging.DEBUG)
    if args.show_benchmark:
        Config.enable_benchmark()
    if args.no_run:
        Config.RUN_CODE = False

    src = load_source(args.file)

    # Lex + Parse
    lexer = Lexer(src)
    parser = Parser(lexer)
    program = parser.parse_program()
    if Config.PARSER_DEBUG or Config.DEBUG:
        dump_ast(program)  # auto filename
    if parser.errors:
        logger.error("Parser errors (%d):", len(parser.errors))
        for e in parser.errors:
            logger.error("  %s", e)
        sys.exit(1)

    # Semantic analysis
    sema = SemanticAnalyzer()
    ok, sem_errors = sema.analyze(program)
    if not ok:
        logger.error("Semantic errors (%d):", len(sem_errors))
        for e in sem_errors:
            logger.error("  %s", e)
        sys.exit(1)

    # Codegen
    codegen = Codegen()
    module = codegen.compile(program)
    if Config.CODEGEN_DEBUG or Config.DEBUG:
        dump_ir(module)

    if Config.RUN_CODE and not args.no_run:
        try:
            res = execute_module(module)
            logger.info("Program exited with %d", res)
        except Exception as e:
            logger.exception("Execution failed: %s", e)
            sys.exit(1)

if __name__ == "__main__":
    main()
