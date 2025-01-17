from Token import Token, TokenType, lookup_ident
from typing import Any

class Lexer:
    def __init__(self, source: str) -> None:
        self.source = source

        self.position: int = -1
        self.read_position: int = 0
        self.line_no: int = 1

        self.current_char: str | None = None

        self.__read_char()
    
    def __read_char(self) -> None:
        if self.read_position >= len(self.source):
            self.current_char = None
        else:
            self.current_char = self.source[self.read_position]

        self.position = self.read_position
        self.read_position += 1

    def __peek_char(self) -> str | None:
        if self.read_position >= len(self.source):
            return None
        
        return self.source[self.read_position]

    def __skip_whitespace(self) -> None:
        while self.current_char in [' ', '\t', '\n', '\r']:
            if self.current_char == '\n':
                self.line_no += 1

            self.__read_char()

    def __new_token(self, tt: TokenType, literal: Any) -> Token:
        return Token(type = tt, literal = literal, line_no = self.line_no, position = self.position)

    def __is_digit(self, ch: str) -> bool:
        return '0' <= ch and ch <= '9'

    def __is_letter(self, ch: str) -> bool:
        return 'a' <= ch and ch <= 'z' \
            or 'A' <= ch and ch <= 'Z' \
            or ch == '_'

    def __read_number(self) -> Token:
        start_pos: int = self.position
        dot_count: int = 0

        output: str = ''
        while self.__is_digit(self.current_char) or self.current_char == '.':
            if self.current_char == '.':
                dot_count += 1
            if dot_count > 1:
                print(f'Too many decimals in number on line {self.line_no}, position {self.position}')
                return self.__new_token(TokenType.ILLEGAL, self.source[start_pos:self.position])
            output += self.source[self.position]
            self.__read_char()

            if self.current_char is None:
                break

        if dot_count == 0:
            return self.__new_token(TokenType.INT, int(output))
        else:
            return self.__new_token(TokenType.FLOAT, float(output))

    def __read_identifier(self) -> str:
        position = self.position

        while self.current_char is not None and (self.__is_letter(self.current_char) or self.current_char.isalnum()):
            self.__read_char()
        
        return self.source[position:self.position]

    def next_token(self) -> Token:
        tok: Token | None = None

        self.__skip_whitespace()

        OPCODE_TABLE = {
            '+': (TokenType.PLUS, self.current_char),
            '-': (TokenType.MINUS, self.current_char),
            '*': (TokenType.ASTERISK, self.current_char),
            '/': (TokenType.SLASH, self.current_char),
            '^': (TokenType.POW, self.current_char),
            '%': (TokenType.MODULUS, self.current_char),
            '=': (TokenType.EQ, self.current_char),
            ':': (TokenType.COLON, self.current_char),
            '(': (TokenType.LPAREN, self.current_char),
            ')': (TokenType.RPAREN, self.current_char),
            '{': (TokenType.LBRACE, self.current_char),
            '}': (TokenType.RBRACE, self.current_char),
            ';': (TokenType.SEMICOLON, self.current_char),
            None: (TokenType.EOF, ''),
        }

        params = OPCODE_TABLE.get(self.current_char)
        
        if params is not None:
            # Check if is function arrow
            if params[0] == TokenType.MINUS:
                if self.__peek_char() == '>':
                    ch = self.current_char
                    self.__read_char()
                    params = TokenType.ARROW, ch + self.current_char

            tok = self.__new_token(*params)
        else:
            if self.__is_letter(self.current_char):
                literal: str = self.__read_identifier()
                tt: TokenType = lookup_ident(literal)
                tok = self.__new_token(tt = tt, literal = literal)
                return tok
            elif self.__is_digit(self.current_char):
                tok = self.__read_number()
                return tok
            else:
                tok = self.__new_token(TokenType.ILLEGAL, self.current_char)

        self.__read_char()
        return tok