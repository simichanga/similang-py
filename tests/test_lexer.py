"""
Thorough unit tests for the Similang lexer.
"""
import pytest
from frontend.lexer import Lexer
from frontend.token import TokenType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _collect_tokens(src: str) -> list:
    """Lex *src* and return all tokens (including EOF)."""
    lex = Lexer(src)
    tokens = []
    while True:
        tok = lex.next_token()
        tokens.append(tok)
        if tok.type == TokenType.EOF:
            break
    return tokens


def _types(src: str) -> list[TokenType]:
    """Return just the token types for *src* (excluding EOF)."""
    return [t.type for t in _collect_tokens(src) if t.type != TokenType.EOF]


# ---------------------------------------------------------------------------
# Basic token recognition
# ---------------------------------------------------------------------------
class TestBasicTokens:
    def test_empty_source(self):
        tokens = _collect_tokens("")
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.EOF

    def test_single_operators(self):
        src = "+ - * / ^ % < > = ! : , ; ( ) { }"
        types = _types(src)
        expected = [
            TokenType.PLUS, TokenType.MINUS, TokenType.ASTERISK, TokenType.SLASH,
            TokenType.POW, TokenType.MODULUS, TokenType.LT, TokenType.GT,
            TokenType.EQ, TokenType.BANG, TokenType.COLON, TokenType.COMMA,
            TokenType.SEMICOLON, TokenType.LPAREN, TokenType.RPAREN,
            TokenType.LBRACE, TokenType.RBRACE,
        ]
        assert types == expected

    def test_two_char_operators(self):
        src = "+= -= *= /= ++ -- -> == != <= >="
        types = _types(src)
        expected = [
            TokenType.PLUS_EQ, TokenType.MINUS_EQ, TokenType.MUL_EQ, TokenType.DIV_EQ,
            TokenType.PLUS_PLUS, TokenType.MINUS_MINUS, TokenType.ARROW,
            TokenType.EQ_EQ, TokenType.NOT_EQ, TokenType.LT_EQ, TokenType.GT_EQ,
        ]
        assert types == expected


# ---------------------------------------------------------------------------
# Keywords and identifiers
# ---------------------------------------------------------------------------
class TestKeywords:
    @pytest.mark.parametrize("kw,expected_type", [
        ("let", TokenType.LET),
        ("fn", TokenType.FN),
        ("return", TokenType.RETURN),
        ("if", TokenType.IF),
        ("else", TokenType.ELSE),
        ("true", TokenType.TRUE),
        ("false", TokenType.FALSE),
        ("while", TokenType.WHILE),
        ("for", TokenType.FOR),
        ("continue", TokenType.CONTINUE),
        ("break", TokenType.BREAK),
    ])
    def test_keyword_recognized(self, kw, expected_type):
        tokens = _collect_tokens(kw)
        assert tokens[0].type == expected_type

    def test_identifier_not_keyword(self):
        tokens = _collect_tokens("myvar")
        assert tokens[0].type == TokenType.IDENT
        assert tokens[0].literal == "myvar"

    def test_identifier_starting_with_underscore(self):
        tokens = _collect_tokens("_private")
        assert tokens[0].type == TokenType.IDENT
        assert tokens[0].literal == "_private"


# ---------------------------------------------------------------------------
# Type keywords (including aliases)
# ---------------------------------------------------------------------------
class TestTypeKeywords:
    @pytest.mark.parametrize("type_kw", [
        "int", "float", "bool", "str", "void",
        "i8", "i16", "i32", "i64",
        "u8", "u16", "u32", "u64",
        "f32", "f64",
        "string", "char",
    ])
    def test_type_keyword_recognized(self, type_kw):
        tokens = _collect_tokens(type_kw)
        assert tokens[0].type == TokenType.TYPE
        assert tokens[0].literal == type_kw


# ---------------------------------------------------------------------------
# Literals
# ---------------------------------------------------------------------------
class TestLiterals:
    def test_integer_literal(self):
        tokens = _collect_tokens("42")
        assert tokens[0].type == TokenType.INT
        assert tokens[0].literal == 42

    def test_float_literal(self):
        tokens = _collect_tokens("3.14")
        assert tokens[0].type == TokenType.FLOAT
        assert tokens[0].literal == 3.14

    def test_string_literal(self):
        tokens = _collect_tokens('"hello world"')
        assert tokens[0].type == TokenType.STRING
        assert tokens[0].literal == "hello world"

    def test_string_escape_sequences(self):
        tokens = _collect_tokens(r'"line1\nline2\ttab"')
        assert tokens[0].literal == "line1\nline2\ttab"

    def test_string_escaped_quote(self):
        tokens = _collect_tokens(r'"say \"hi\""')
        assert tokens[0].literal == 'say "hi"'

    def test_unterminated_string_raises(self):
        with pytest.raises(SyntaxError, match="Unterminated string"):
            _collect_tokens('"hello')

    def test_zero_literal(self):
        tokens = _collect_tokens("0")
        assert tokens[0].type == TokenType.INT
        assert tokens[0].literal == 0


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------
class TestComments:
    def test_single_line_comment(self):
        src = "let a // this is a comment\nlet b"
        types = _types(src)
        # should see: LET IDENT LET IDENT
        assert types == [TokenType.LET, TokenType.IDENT, TokenType.LET, TokenType.IDENT]

    def test_multiline_comment(self):
        src = "let /* this\nis a\ncomment */ a"
        types = _types(src)
        assert types == [TokenType.LET, TokenType.IDENT]


# ---------------------------------------------------------------------------
# Line tracking
# ---------------------------------------------------------------------------
class TestLineTracking:
    def test_line_numbers(self):
        src = "let x\nlet y\nlet z"
        tokens = _collect_tokens(src)
        assert tokens[0].line_no == 1  # let
        assert tokens[2].line_no == 2  # let (second)
        assert tokens[4].line_no == 3  # let (third)


# ---------------------------------------------------------------------------
# Full statement
# ---------------------------------------------------------------------------
class TestFullStatements:
    def test_let_statement_tokens(self):
        src = "let x: int = 10;"
        types = _types(src)
        expected = [
            TokenType.LET, TokenType.IDENT, TokenType.COLON,
            TokenType.TYPE, TokenType.EQ, TokenType.INT, TokenType.SEMICOLON,
        ]
        assert types == expected

    def test_function_declaration_tokens(self):
        src = "fn add(a: int, b: int) -> int { return a + b; }"
        types = _types(src)
        assert types[0] == TokenType.FN
        assert TokenType.ARROW in types
        assert TokenType.RETURN in types

    def test_let_with_type_alias(self):
        """i32 should lex as TYPE, just like int."""
        src = "let x: i32 = 5;"
        types = _types(src)
        expected = [
            TokenType.LET, TokenType.IDENT, TokenType.COLON,
            TokenType.TYPE, TokenType.EQ, TokenType.INT, TokenType.SEMICOLON,
        ]
        assert types == expected
