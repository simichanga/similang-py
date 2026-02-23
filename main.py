"""
Top-level driver for Similang (refactored layout).
Usage:
    python main.py path/to/file.simi [--no-run] [--debug] [--show-benchmark]
                                      [--opt-level 0-3] [--size-level 0-2]
                                      [--no-ast-opt] [--no-llvm-opt]

This script:
 - reads the source file
 - lexes and parses into AST
 - runs semantic analysis
 - runs AST-level optimizations (constant folding, DCE, constant propagation)
 - generates LLVM IR
 - applies LLVM optimization passes
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
from middle.optimizer import ASTOptimizer
from backend.codegen import Codegen
from util.config import Config
from util.executor import execute_module
from util.debug import dump_ast, dump_tokens, dump_ir
from util.diagnostics import DiagnosticEngine
from util.source_map import SourceMap

logging.basicConfig(level=logging.DEBUG if Config.DEBUG else logging.INFO)
logger = logging.getLogger("similang")

def parse_args():
    p = argparse.ArgumentParser(description="Similang compiler driver")
    p.add_argument("file", help="Source file (.simi)")
    p.add_argument("--no-run", action="store_true", help="Do not execute the produced code")
    p.add_argument("--debug", action="store_true", help="Enable debug flags")
    p.add_argument("--show-benchmark", action="store_true", help="Show benchmark info")
    p.add_argument("--opt-level", "-O", type=int, default=2, choices=[0, 1, 2, 3],
                   help="Optimization level (0=none, 1=basic, 2=standard, 3=aggressive). Default: 2")
    p.add_argument("--size-level", "-Os", type=int, default=0, choices=[0, 1, 2],
                   help="Size optimization level (0=none, 1=size, 2=min-size). Default: 0")
    p.add_argument("--no-ast-opt", action="store_true", help="Disable AST-level optimizations")
    p.add_argument("--no-llvm-opt", action="store_true", help="Disable LLVM IR-level optimizations")
    p.add_argument("--source-map", action="store_true", help="Generate a source map (.simi.map.json)")
    p.add_argument("--show-source-map", action="store_true",
                   help="Print the source map table to stdout")
    p.add_argument("--emit-ir", action="store_true",
                   help="Print the generated LLVM IR to stdout")
    p.add_argument("--emit-source-map", action="store_true",
                   help="Print the source map as JSON to stdout")
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

    # Optimization configuration
    Config.OPT_LEVEL = args.opt_level
    Config.SIZE_LEVEL = args.size_level
    if args.no_ast_opt:
        Config.AST_OPT = False
    if args.no_llvm_opt:
        Config.LLVM_OPT = False

    src = load_source(args.file)

    # Central diagnostics engine
    diag = DiagnosticEngine(source_text=src, filename=args.file)

    # Lex + Parse
    lexer = Lexer(src)
    parser = Parser(lexer, diag=diag)
    program = parser.parse_program()
    if Config.PARSER_DEBUG or Config.DEBUG:
        dump_ast(program)  # auto filename
    if parser.error_collector.has_errors():
        diag.summary()
        sys.exit(1)

    # Semantic analysis
    sema = SemanticAnalyzer()
    ok, sem_errors = sema.analyze(program)
    if not ok:
        for e in sem_errors:
            diag.error(e)
        diag.summary()
        sys.exit(1)

    # AST-level optimization
    if Config.AST_OPT and Config.OPT_LEVEL > 0:
        optimizer = ASTOptimizer(opt_level=Config.OPT_LEVEL)
        program, opt_stats = optimizer.optimize(program)
        if Config.OPT_DEBUG or Config.DEBUG:
            logger.info("AST optimizations: %s", opt_stats)

    # Source map (created before codegen so codegen can record anchors)
    smap = None
    if args.source_map or args.show_source_map or args.emit_source_map:
        smap = SourceMap(filename=args.file, source_text=src)

    # Codegen
    codegen = Codegen(source_map=smap)
    module = codegen.compile(program)
    if Config.CODEGEN_DEBUG or Config.DEBUG:
        dump_ir(module)

    if codegen.errors:
        for e in codegen.errors:
            diag.error(e)
        diag.summary()
        sys.exit(1)

    # Emit IR to stdout if requested
    if args.emit_ir:
        print(str(module))

    # Write / display source map
    if smap:
        if args.source_map:
            map_path = Path(args.file).with_suffix(".simi.map.json")
            smap.write_json(map_path)
            logger.info("Source map written to %s (%d mappings, %.0f%% coverage)",
                        map_path, len(smap), smap.coverage * 100)
        if args.show_source_map:
            print()
            print(smap.format_table())
            print()
        if args.emit_source_map:
            import json as _json
            print(_json.dumps(smap.to_json()))

    if Config.RUN_CODE and not args.no_run:
        try:
            res = execute_module(module)
            logger.info("Program exited with %d", res)
        except Exception as e:
            logger.exception("Execution failed: %s", e)
            sys.exit(1)

if __name__ == "__main__":
    main()
