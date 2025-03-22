from enum import Enum
from typing import Any, Dict, Optional, Set, Union

class TokenType(Enum):
    # Special Tokens
    EOF = 'EOF'
    ILLEGAL = 'ILLEGAL'

    # Data Types
    IDENT = 'IDENT'
    INT = 'INT'
    FLOAT = 'FLOAT'
    STRING = 'STRING'

    # Arithmetic Symbols
    PLUS = 'PLUS'
    MINUS = 'MINUS'
    ASTERISK = 'ASTERISK'
    SLASH = 'SLASH'
    POW = 'POW'
    MODULUS = 'MODULUS'

    # Assignment Symbols
    EQ = 'EQ'
    PLUS_EQ = 'PLUS_EQ'
    MINUS_EQ = 'MINUS_EQ'
    MUL_EQ = 'MUL_EQ'
    DIV_EQ = 'DIV_EQ'

    # Comparison Symbols
    LT = '<'
    GT = '>'
    EQ_EQ = '=='
    NOT_EQ = '!='
    LT_EQ = '<='
    GT_EQ = '>='

    # Symbols
    COLON = 'COLON'
    COMMA = 'COMMA'
    SEMICOLON = 'SEMICOLON'
    ARROW = 'ARROW'
    LPAREN = 'LPAREN'
    RPAREN = 'RPAREN'
    LBRACE = 'LBRACE'
    RBRACE = 'RBRACE'

    # Prefix Symbols
    BANG = 'BANG'

    # Postfix Symbols
    PLUS_PLUS = 'PLUS_PLUS'
    MINUS_MINUS = 'MINUS_MINUS'

    # Keywords
    LET = 'LET'
    FN = 'FN'
    RETURN = 'RETURN'
    IF = 'IF'
    ELSE = 'ELSE'
    TRUE = 'TRUE'
    FALSE = 'FALSE'
    WHILE = 'WHILE'
    CONTINUE = 'CONTINUE'
    BREAK = 'BREAK'
    FOR = 'FOR'

    # Typing
    TYPE = 'TYPE'

class Token:
    def __init__(self, type_: TokenType, literal: Union[int, float, str], line_no: int, position: int) -> None:
        """
        Initialize Token object.

        :param type_: TokenType enum value, representing the token type.
        :param literal: The literal value of the token, can be int, float, or str.
        :param line_no: The line number where the token is located.
        :param position: The position of the token within the line.
        """
        self.type = type_
        self.literal = literal
        self.line_no = line_no
        self.position = position

    def __str__(self) -> str:
        return f'Token[{self.type} : {self.literal} : Line {self.line_no} : Position {self.position}]'

    def __repr__(self) -> str:
        return str(self)

KEYWORDS: Dict[str, TokenType] = {
    'let': TokenType.LET,
    'fn': TokenType.FN,
    'return': TokenType.RETURN,
    'if': TokenType.IF,
    'else': TokenType.ELSE,
    'true': TokenType.TRUE,
    'false': TokenType.FALSE,
    'while': TokenType.WHILE,
    'for': TokenType.FOR,
    'continue': TokenType.CONTINUE,
    'break': TokenType.BREAK,
}

TYPE_KEYWORDS: Set[str] = {'bool', 'int', 'float', 'str', 'void'}

def lookup_ident(ident: str) -> TokenType:
    """
    Look up the corresponding TokenType for an identifier.

    :param ident: Identifier string.
    :return: Corresponding TokenType enum value.
    """
    if not isinstance(ident, str):
        raise TypeError("Input must be a string")

    # Check if it's a keyword
    if tt := KEYWORDS.get(ident):
        return tt

    # Check if it's a type keyword
    if ident in TYPE_KEYWORDS:
        return TokenType.TYPE

    # Default return identifier type
    return TokenType.IDENT