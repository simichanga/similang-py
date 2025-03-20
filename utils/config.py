class Config:
    # Debugging Flags
    DEBUG = True  # General debug flag
    LEXER_DEBUG = False
    PARSER_DEBUG = True
    COMPILER_DEBUG = True

    # Execution Flags
    RUN_CODE = True

    @classmethod
    def enable_all_debug(cls):
        """Enable all debugging flags."""
        cls.DEBUG = True
        cls.LEXER_DEBUG = True
        cls.PARSER_DEBUG = True
        cls.COMPILER_DEBUG = True

    @classmethod
    def disable_all_debug(cls):
        """Disable all debugging flags."""
        cls.DEBUG = False
        cls.LEXER_DEBUG = False
        cls.PARSER_DEBUG = False
        cls.COMPILER_DEBUG = False
