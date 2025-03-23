class Config:
    DEBUG = False
    LEXER_DEBUG = False
    PARSER_DEBUG = False
    COMPILER_DEBUG = False
    RUN_CODE = True
    SHOW_BENCHMARK = False
    SHOW_EXECUTION_OUTPUT = False

    @classmethod
    def enable_all_debug(cls):
        """Enable all debugging flags."""
        cls.DEBUG = True
        cls.LEXER_DEBUG = True
        cls.PARSER_DEBUG = True
        cls.COMPILER_DEBUG = True
        cls.SHOW_BENCHMARK = True
        cls.SHOW_EXECUTION_OUTPUT = True

    @classmethod
    def disable_all_debug(cls):
        """Disable all debugging flags."""
        cls.DEBUG = False
        cls.LEXER_DEBUG = False
        cls.PARSER_DEBUG = False
        cls.COMPILER_DEBUG = False
        cls.SHOW_BENCHMARK = False
        cls.SHOW_EXECUTION_OUTPUT = False

    @classmethod
    def enable_benchmark(cls):
        """Enable benchmark output."""
        cls.SHOW_BENCHMARK = True

    @classmethod
    def disable_benchmark(cls):
        """Disable benchmark output."""
        cls.SHOW_BENCHMARK = False

    @classmethod
    def enable_execution_output(cls):
        """Enable execution output."""
        cls.SHOW_EXECUTION_OUTPUT = True

    @classmethod
    def disable_execution_output(cls):
        """Disable execution output."""
        cls.SHOW_EXECUTION_OUTPUT = False
