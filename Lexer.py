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
        """ Advances the lexer by one character. """
        self.current_char = self.source[self.read_position] if self.read_position < len(self.source) else None
        self.position = self.read_position
        self.read_position += 1

    def __peek_char(self) -> str | None:
        """ Peeks at the next character without advancing. """
        return self.source[self.read_position] if self.read_position < len(self.source) else None

    def __match_next(self, expected: str) -> bool:
        """ Matches the next character against an expected value and consumes it if matched. """
        if self.__peek_char() == expected:
            self.__read_char()
            return True
        return False

    def __skip_comment(self) -> None:
        """ Skips over comments (both single-line `//` and multi-line `/* */`). """
        if self.__match_next('/'):
            while self.current_char and self.current_char != '\n':
                self.__read_char()
        elif self.__match_next('*'):
            while self.current_char:
                if self.current_char == '*' and self.__match_next('/'):
                    self.__read_char()
                    break
                if self.current_char == '\n':
                    self.line_no += 1
                self.__read_char()

    def __skip_whitespace(self) -> None:
        """ Skips over whitespace and tracks newlines. """
        while self.current_char and self.current_char.isspace():
            if self.current_char == '\n':
                self.line_no += 1
            self.__read_char()

    def __new_token(self, tt: TokenType, literal: Any) -> Token:
        """ Creates a new token with the current position and line number. """
        return Token(type_= tt, literal = literal, line_no = self.line_no, position = self.position)

    @staticmethod
    def __is_digit(ch: str) -> bool:
        return '0' <= ch <= '9'

    @staticmethod
    def __is_letter(ch: str) -> bool:
        return 'a' <= ch <= 'z' \
            or 'A' <= ch <= 'Z' \
            or ch == '_'

    def __read_number(self) -> Token:
        """ Reads an integer or float. """
        start_pos = self.position
        has_dot = False

        while self.current_char and (self.current_char.isdigit() or (self.current_char == '.' and not has_dot)):
            if self.current_char == '.':
                has_dot = True
            self.__read_char()

        num_str = self.source[start_pos:self.position]
        return self.__new_token(
            TokenType.FLOAT if has_dot else TokenType.INT,
            float(num_str) if has_dot else int(num_str)
        )

    def __read_identifier(self) -> str:
        """ Reads an identifier or keyword. """
        position = self.position

        while self.current_char is not None and (self.__is_letter(self.current_char) or self.current_char.isalnum()):
            self.__read_char()

        return self.source[position:self.position]

    def __read_string(self) -> str:
        """ Reads a string, handling escape sequences. """
        start_pos = self.position + 1
        escaped = False
        result = ""

        self.__read_char()
        while self.current_char and (escaped or self.current_char != '"'):
            if self.current_char == '\\' and not escaped:
                escaped = True
            else:
                if escaped:
                    match self.current_char:
                        case 'n': result += '\n'
                        case 't': result += '\t'
                        case '\\': result += '\\'
                        case '"': result += '"'
                        case _: result += "\\" + self.current_char
                    escaped = False
                else:
                    result += self.current_char
            self.__read_char()

        if self.current_char is None:
            raise SyntaxError(f"Unterminated string at line {self.line_no}")

        self.__read_char()
        return self.__new_token(TokenType.STRING, result)

    def next_token(self) -> Token | str:
        """ Retrieves the next token from the source code. """
        self.__skip_whitespace()

        # Handle comments
        if self.current_char == '/' and (self.__peek_char() == '/' or self.__peek_char() == '*'):
            self.__skip_comment()
            return self.next_token()

        tok = None

        match self.current_char:
            case '+':
                if self.__peek_char() == '=':
                    self.__read_char()  # Consume the '='
                    tok = self.__new_token(TokenType.PLUS_EQ, '+=')
                elif self.__peek_char() == '+':
                    self.__read_char()  # Consume the '+'
                    tok = self.__new_token(TokenType.PLUS_PLUS, '++')
                else:
                    tok = self.__new_token(TokenType.PLUS, '+')
            case '-':
                if self.__peek_char() == '=':
                    self.__read_char()  # Consume the '='
                    tok = self.__new_token(TokenType.MINUS_EQ, '-=')
                elif self.__peek_char() == '-':
                    self.__read_char()  # Consume the '-'
                    tok = self.__new_token(TokenType.MINUS_MINUS, '--')
                elif self.__peek_char() == '>':
                    self.__read_char()  # Consume the '>'
                    tok = self.__new_token(TokenType.ARROW, '->')
                else:
                    tok = self.__new_token(TokenType.MINUS, '-')
            case '*':
                if self.__peek_char() == '=':
                    self.__read_char()  # Consume the '='
                    tok = self.__new_token(TokenType.MUL_EQ, '*=')
                else:
                    tok = self.__new_token(TokenType.ASTERISK, '*')
            case '/':
                if self.__peek_char() == '=':
                    self.__read_char()  # Consume the '='
                    tok = self.__new_token(TokenType.DIV_EQ, '/=')
                else:
                    tok = self.__new_token(TokenType.SLASH, '/')
            case '^': tok = self.__new_token(TokenType.POW, self.current_char)
            case '%': tok = self.__new_token(TokenType.MODULUS, self.current_char)
            case '<':
                if self.__peek_char() == '=':
                    self.__read_char()  # Consume the '='
                    tok = self.__new_token(TokenType.LT_EQ, '<=')
                else:
                    tok = self.__new_token(TokenType.LT, '<')
            case '>':
                if self.__peek_char() == '=':
                    self.__read_char()  # Consume the '='
                    tok = self.__new_token(TokenType.GT_EQ, '>=')
                else:
                    tok = self.__new_token(TokenType.GT, '>')
            case '=':
                if self.__peek_char() == '=':
                    self.__read_char()  # Consume the second '='
                    tok = self.__new_token(TokenType.EQ_EQ, '==')
                else:
                    tok = self.__new_token(TokenType.EQ, '=')
            case '!':
                if self.__peek_char() == '=':
                    self.__read_char()  # Consume the '='
                    tok = self.__new_token(TokenType.NOT_EQ, '!=')
                else:
                    tok = self.__new_token(TokenType.BANG, '!')
            case ':': tok = self.__new_token(TokenType.COLON, ':')
            case ',': tok = self.__new_token(TokenType.COMMA, ',')
            case '"': return self.__read_string()
            case '(': tok = self.__new_token(TokenType.LPAREN, '(')
            case ')': tok = self.__new_token(TokenType.RPAREN, ')')
            case '{': tok = self.__new_token(TokenType.LBRACE, '{')
            case '}': tok = self.__new_token(TokenType.RBRACE, '}')
            case ';': tok = self.__new_token(TokenType.SEMICOLON, ';')
            case None: tok = self.__new_token(TokenType.EOF, '')
            case _:
                if self.current_char.isalpha() or self.current_char == '_':
                    literal = self.__read_identifier()
                    return self.__new_token(lookup_ident(literal), literal)
                elif self.current_char.isdigit():
                    return self.__read_number()
                else:
                    tok = self.__new_token(TokenType.ILLEGAL, self.current_char)

        self.__read_char()
        return tok