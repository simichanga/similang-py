import pytest
from frontend.lexer import Lexer
from frontend.token import TokenType

def test_lexer_simple_tokens():
    src = 'let a: int = 10; // comment\nfn foo() -> int { return 0; }'
    lex = Lexer(src)
    tokens = []
    while True:
        tok = lex.next_token()
        tokens.append(tok)
        if tok.type == TokenType.EOF:
            break

    # quick assertions on token sequence (first tokens)
    assert tokens[0].type == TokenType.LET
    # find the 'fn' token somewhere later
    assert any(t.type == TokenType.FN for t in tokens)
    # ensure comment removed -> semicolon token exists
    assert any(t.type == TokenType.SEMICOLON for t in tokens)
