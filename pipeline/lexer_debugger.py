from Lexer import Lexer

def debug_lexer(code: str) -> None:
    print('===== LEXER DEBUG =====')
    lexer = Lexer(source=code)
    while lexer.current_char is not None:
        print(lexer.next_token())
