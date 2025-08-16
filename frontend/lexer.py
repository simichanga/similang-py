from __future__ import annotations
from typing import Optional, Any
from frontend.token import Token, TokenType, lookup_ident


class Lexer:
    """A small, robust lexer for Similang (supports // and /* */ comments, strings, numbers, identifiers)."""

    def __init__(self, source: str) -> None:
        self.source = source or ""
        self.pos: int = -1           # current index into source (points to current_char)
        self.current_char: Optional[str] = None
        self.line_no: int = 1
        self.col: int = 0
        self._read_char()

    # ---- low-level helpers ----
    def _read_char(self) -> None:
        """Advance one character; set current_char or None at EOF."""
        self.pos += 1
        if self.pos >= len(self.source):
            self.current_char = None
            self.col = 0
        else:
            self.current_char = self.source[self.pos]
            self.col += 1

    def _peek_char(self) -> Optional[str]:
        nxt = self.pos + 1
        return self.source[nxt] if nxt < len(self.source) else None

    def _match_next(self, expected: str) -> bool:
        if self._peek_char() == expected:
            self._read_char()
            return True
        return False

    # ---- scanning primitives ----
    def _is_digit(self, ch: str) -> bool:
        return '0' <= ch <= '9'

    def _is_letter(self, ch: str) -> bool:
        return ch.isalpha() or ch == '_'

    def _skip_whitespace(self) -> None:
        while self.current_char is not None and self.current_char.isspace():
            if self.current_char == '\n':
                self.line_no += 1
                self.col = 0
            self._read_char()

    def _skip_comment(self) -> None:
        # supports // single-line and /* ... */ multi-line
        if self._match_next('/'):
            # single-line: consume until newline or EOF
            self._read_char()  # move past the second '/'
            while self.current_char is not None and self.current_char != '\n':
                self._read_char()
        elif self._match_next('*'):
            # multi-line: consume until */
            self._read_char()  # move past the first char after '/*'
            while self.current_char is not None:
                if self.current_char == '*' and self._peek_char() == '/':
                    self._read_char()  # move to '/'
                    self._read_char()  # move past '/'
                    break
                if self.current_char == '\n':
                    self.line_no += 1
                    self.col = 0
                self._read_char()

    def _new_token(self, tt: TokenType, literal: Any) -> Token:
        return Token(type=tt, literal=literal, line_no=self.line_no, position=self.pos)

    # ---- higher-level scanners ----
    def _read_number(self) -> Token:
        buf = []
        has_dot = False
        # allow leading digits and at most one dot
        while self.current_char is not None and (self._is_digit(self.current_char) or (self.current_char == '.' and not has_dot)):
            if self.current_char == '.':
                has_dot = True
            buf.append(self.current_char)
            self._read_char()
        s = ''.join(buf)
        if s == '':
            return self._new_token(TokenType.ILLEGAL, '')
        return self._new_token(TokenType.FLOAT if has_dot else TokenType.INT, float(s) if has_dot else int(s))

    def _read_identifier(self) -> str:
        buf = []
        while self.current_char is not None and (self._is_letter(self.current_char) or self.current_char.isdigit()):
            buf.append(self.current_char)
            self._read_char()
        return ''.join(buf)

    def _read_string(self) -> Token:
        # current_char is '"', consume opening quote
        self._read_char()
        buf = []
        escaped = False
        while self.current_char is not None and (escaped or self.current_char != '"'):
            ch = self.current_char
            if not escaped and ch == '\\':
                escaped = True
                self._read_char()
                continue
            if escaped:
                # handle common escapes
                match ch:
                    case 'n': buf.append('\n')
                    case 't': buf.append('\t')
                    case '\\': buf.append('\\')
                    case '"': buf.append('"')
                    case 'r': buf.append('\r')
                    case _: buf.append(ch)  # unknown escape -> keep raw
                escaped = False
            else:
                buf.append(ch)
            self._read_char()

        if self.current_char is None:
            raise SyntaxError(f"Unterminated string literal (line {self.line_no})")

        # consume closing quote
        self._read_char()
        return self._new_token(TokenType.STRING, ''.join(buf))

    # ---- public API ----
    def next_token(self) -> Token:
        """Return next token; does not return None (EOF token used)."""
        # skip whitespace and comments
        self._skip_whitespace()

        # comments: they start with '/'
        if self.current_char == '/' and (self._peek_char() in ('/', '*')):
            self._skip_comment()
            # after skipping a comment, find next token
            self._skip_whitespace()
            if self.current_char is None:
                return self._new_token(TokenType.EOF, '')
        pos_snapshot = self.pos

        if self.current_char is None:
            return self._new_token(TokenType.EOF, '')

        ch = self.current_char

        # two-character tokens first (lookahead)
        if ch == '+':
            if self._peek_char() == '=':
                self._read_char()
                tok = self._new_token(TokenType.PLUS_EQ, '+=')
            elif self._peek_char() == '+':
                self._read_char()
                tok = self._new_token(TokenType.PLUS_PLUS, '++')
            else:
                tok = self._new_token(TokenType.PLUS, '+')
        elif ch == '-':
            if self._peek_char() == '=':
                self._read_char()
                tok = self._new_token(TokenType.MINUS_EQ, '-=')
            elif self._peek_char() == '-':
                self._read_char()
                tok = self._new_token(TokenType.MINUS_MINUS, '--')
            elif self._peek_char() == '>':
                self._read_char()
                tok = self._new_token(TokenType.ARROW, '->')
            else:
                tok = self._new_token(TokenType.MINUS, '-')
        elif ch == '*':
            if self._peek_char() == '=':
                self._read_char()
                tok = self._new_token(TokenType.MUL_EQ, '*=')
            else:
                tok = self._new_token(TokenType.ASTERISK, '*')
        elif ch == '/':
            if self._peek_char() == '=':
                self._read_char()
                tok = self._new_token(TokenType.DIV_EQ, '/=')
            else:
                tok = self._new_token(TokenType.SLASH, '/')
        elif ch == '^':
            tok = self._new_token(TokenType.POW, '^')
        elif ch == '%':
            tok = self._new_token(TokenType.MODULUS, '%')
        elif ch == '<':
            if self._peek_char() == '=':
                self._read_char()
                tok = self._new_token(TokenType.LT_EQ, '<=')
            else:
                tok = self._new_token(TokenType.LT, '<')
        elif ch == '>':
            if self._peek_char() == '=':
                self._read_char()
                tok = self._new_token(TokenType.GT_EQ, '>=')
            else:
                tok = self._new_token(TokenType.GT, '>')
        elif ch == '=':
            if self._peek_char() == '=':
                self._read_char()
                tok = self._new_token(TokenType.EQ_EQ, '==')
            else:
                tok = self._new_token(TokenType.EQ, '=')
        elif ch == '!':
            if self._peek_char() == '=':
                self._read_char()
                tok = self._new_token(TokenType.NOT_EQ, '!=')
            else:
                tok = self._new_token(TokenType.BANG, '!')
        elif ch == ':':
            tok = self._new_token(TokenType.COLON, ':')
        elif ch == ',':
            tok = self._new_token(TokenType.COMMA, ',')
        elif ch == '"':
            tok = self._read_string()
            # _read_string already advanced past the closing quote
            return tok
        elif ch == '(':
            tok = self._new_token(TokenType.LPAREN, '(')
        elif ch == ')':
            tok = self._new_token(TokenType.RPAREN, ')')
        elif ch == '{':
            tok = self._new_token(TokenType.LBRACE, '{')
        elif ch == '}':
            tok = self._new_token(TokenType.RBRACE, '}')
        elif ch == '[':
            tok = self._new_token(TokenType.LBRACKET, '[')
        elif ch == ']':
            tok = self._new_token(TokenType.RBRACKET, ']')
        elif ch == ';':
            tok = self._new_token(TokenType.SEMICOLON, ';')
        elif ch.isalpha() or ch == '_':
            literal = self._read_identifier()
            tok_type = lookup_ident(literal)
            # lookup_ident returns TYPE for type keywords
            return self._new_token(tok_type, literal)
        elif ch.isdigit():
            return self._read_number()
        else:
            tok = self._new_token(TokenType.ILLEGAL, ch)

        # advance past current character
        self._read_char()
        return tok
