class Config:
    DEBUG = False
    DEBUG_DUMP_DIR = "debug"  # directory where dumps are written
    LEXER_DEBUG = False
    PARSER_DEBUG = False
    SEMANTIC_DEBUG = False
    CODEGEN_DEBUG = False
    RUN_CODE = True
    SHOW_BENCHMARK = False
    SHOW_EXECUTION_OUTPUT = False

    # Optimization settings
    OPT_LEVEL: int = 0          # 0 = none, 1 = basic, 2 = standard, 3 = aggressive
    SIZE_LEVEL: int = 0         # 0 = none, 1 = size, 2 = min-size
    AST_OPT: bool = True        # run AST-level optimizations (constant folding, DCE, etc.)
    LLVM_OPT: bool = True       # run LLVM-level optimization passes
    OPT_DEBUG: bool = False     # print optimizer diagnostics
    SOURCEMAP: bool = False     # generate source map by default

    @classmethod
    def enable_all_debug(cls):
        cls.DEBUG = True
        cls.LEXER_DEBUG = True
        cls.PARSER_DEBUG = True
        cls.SEMANTIC_DEBUG = True
        cls.CODEGEN_DEBUG = True
        cls.SHOW_BENCHMARK = True
        cls.SHOW_EXECUTION_OUTPUT = True
        cls.OPT_DEBUG = True

    @classmethod
    def disable_all_debug(cls):
        cls.DEBUG = False
        cls.LEXER_DEBUG = False
        cls.PARSER_DEBUG = False
        cls.SEMANTIC_DEBUG = False
        cls.CODEGEN_DEBUG = False
        cls.SHOW_BENCHMARK = False
        cls.SHOW_EXECUTION_OUTPUT = False
        cls.OPT_DEBUG = False

    @classmethod
    def enable_benchmark(cls):
        cls.SHOW_BENCHMARK = True

    @classmethod
    def enable_execution_output(cls):
        cls.SHOW_EXECUTION_OUTPUT = True
