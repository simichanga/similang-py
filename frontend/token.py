from __future__ import annotations
from enum import Enum
from dataclasses import dataclass
from typing import Union, Dict, Set

class TokenType(Enum):
    # Special Tokens
    EOF = 'EOF'
    ILLEGAL = 'ILLEGAL'

    # Data Types / Literals
    IDENT = 'IDENT'
    INT = 'INT'
    FLOAT = 'FLOAT'
    STRING = 'STRING'

    # Arithmetic
    PLUS = '+'
    MINUS = '-'
    ASTERISK = '*'
    SLASH = '/'
    POW = '^'
    MODULUS = '%'

    # Assignment
    EQ = '='
    PLUS_EQ = '+='
    MINUS_EQ = '-='
    MUL_EQ = '*='
    DIV_EQ = '/='

    # Comparison
    LT = '<'
    GT = '>'
    EQ_EQ = '=='
    NOT_EQ = '!='
    LT_EQ = '<='
    GT_EQ = '>='

    # Punctuation
    COLON = ':'
    COMMA = ','
    SEMICOLON = ';'
    ARROW = '->'
    LPAREN = '('
    RPAREN = ')'
    LBRACE = '{'
    RBRACE = '}'
    LBRACKET = '['
    RBRACKET = ']'
    DOT = '.'

    # Prefix / Postfix
    BANG = '!'
    PLUS_PLUS = '++'
    MINUS_MINUS = '--'

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
    STRUCT = 'STRUCT'

    # Types
    TYPE = 'TYPE'


@dataclass
class Token:
    type: TokenType
    literal: Union[str, int, float]
    line_no: int
    position: int
    col: int = 0

    def __str__(self) -> str:
        return f"Token[{self.type} : {self.literal!r} : Line {self.line_no} : Pos {self.position}]"

    __repr__ = __str__


# Keywords & type keywords
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
    'struct': TokenType.STRUCT,
    'continue': TokenType.CONTINUE,
    'break': TokenType.BREAK,
}

# Canonical type names and their aliases.
# All of these are recognized as TYPE tokens by the lexer.
TYPE_KEYWORDS: Set[str] = {
    # Canonical names
    'bool', 'int', 'float', 'str', 'void',
    # Integer aliases
    'i8', 'i16', 'i32', 'i64',
    'u8', 'u16', 'u32', 'u64',
    # Float aliases
    'f32', 'f64',
    # Other aliases
    'string', 'char',
}


def lookup_ident(ident: str) -> TokenType:
    if not isinstance(ident, str):
        raise TypeError("identifier must be str")
    if kw := KEYWORDS.get(ident):
        return kw
    if ident in TYPE_KEYWORDS:
        return TokenType.TYPE
    return TokenType.IDENT
