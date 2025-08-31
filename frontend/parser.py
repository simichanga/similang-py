from __future__ import annotations
from typing import Callable, Dict, Optional, List, Any
from enum import IntEnum, auto

from frontend.lexer import Lexer
from frontend.token import TokenType, Token
from frontend import ast as A
from util.errors import ErrorCollector


class Precedence(IntEnum):
    LOWEST = 0
    EQUALS = auto()        # == or !=
    LESSGREATER = auto()   # > or <
    SUM = auto()           # + -
    PRODUCT = auto()       # * /
    EXPONENT = auto()      # ^
    PREFIX = auto()        # -X or !X
    CALL = auto()          # function calls
    INDEX = auto()         # postfix ++/-- (treated high)


# precedence table
PRECEDENCES: Dict[TokenType, Precedence] = {
    TokenType.PLUS: Precedence.SUM,
    TokenType.MINUS: Precedence.SUM,
    TokenType.SLASH: Precedence.PRODUCT,
    TokenType.ASTERISK: Precedence.PRODUCT,
    TokenType.MODULUS: Precedence.PRODUCT,
    TokenType.POW: Precedence.EXPONENT,

    TokenType.EQ_EQ: Precedence.EQUALS,
    TokenType.NOT_EQ: Precedence.EQUALS,
    TokenType.LT: Precedence.LESSGREATER,
    TokenType.GT: Precedence.LESSGREATER,
    TokenType.LT_EQ: Precedence.LESSGREATER,
    TokenType.GT_EQ: Precedence.LESSGREATER,

    TokenType.LPAREN: Precedence.CALL,

    TokenType.PLUS_PLUS: Precedence.INDEX,
    TokenType.MINUS_MINUS: Precedence.INDEX,
}


class Parser:
    """
    Pratt/Top-down operator precedence parser for Similang. Produces AST nodes from frontend.ast.
    Collects errors in self.errors (does not raise).
    """

    def __init__(self, lexer: Lexer) -> None:
        self.lexer = lexer
        self.error_collector = ErrorCollector()
        self.current_token: Optional[Token] = None
        self.peek_token: Optional[Token] = None

        # the prefix/infix parse function tables:
        self.prefix_parse_fns: Dict[TokenType, Callable[[], Optional[A.Expression]]] = {
            TokenType.IDENT: self._parse_identifier,
            TokenType.INT: self._parse_int_literal,
            TokenType.FLOAT: self._parse_float_literal,
            TokenType.LPAREN: self._parse_grouped_expression,
            TokenType.TRUE: self._parse_boolean,
            TokenType.FALSE: self._parse_boolean,
            TokenType.STRING: self._parse_string_literal,
            TokenType.MINUS: self._parse_prefix_expression,
            TokenType.BANG: self._parse_prefix_expression,
        }

        # infix defaults to generic infix parser
        self.infix_parse_fns: Dict[TokenType, Callable[[A.Expression], A.Expression]] = {
            tt: self._parse_infix_expression for tt in TokenType
        }
        # overrides
        self.infix_parse_fns[TokenType.LPAREN] = self._parse_call_expression
        self.infix_parse_fns[TokenType.PLUS_PLUS] = self._parse_postfix_expression
        self.infix_parse_fns[TokenType.MINUS_MINUS] = self._parse_postfix_expression
        self.infix_parse_fns[TokenType.PLUS_EQ] = self._parse_assignment_expression
        self.infix_parse_fns[TokenType.MINUS_EQ] = self._parse_assignment_expression
        self.infix_parse_fns[TokenType.MUL_EQ] = self._parse_assignment_expression
        self.infix_parse_fns[TokenType.DIV_EQ] = self._parse_assignment_expression

        # prime tokens
        self._next_token()
        self._next_token()

    # ---- token helpers ----
    def _next_token(self) -> None:
        self.current_token = self.peek_token
        self.peek_token = self.lexer.next_token()

    def _current_is(self, tt: TokenType) -> bool:
        return self.current_token and self.current_token.type == tt

    def _peek_is(self, tt: TokenType) -> bool:
        return self.peek_token and self.peek_token.type == tt

    def _expect_peek(self, tt: TokenType) -> bool:
        if self._peek_is(tt):
            self._next_token()
            return True
        self._peek_error(tt)
        return False

    def _peek_error(self, tt: TokenType) -> None:
        got = self.peek_token.type if self.peek_token else None
        self.error_collector.add_error(
            f"Expected next token to be {tt}, got {got}",
            line=self.peek_token.line_no if self.peek_token else None
        )

    def _current_precedence(self) -> Precedence:
        return PRECEDENCES.get(self.current_token.type, Precedence.LOWEST)

    def _peek_precedence(self) -> Precedence:
        return PRECEDENCES.get(self.peek_token.type, Precedence.LOWEST)

    def _peek_assignment_op(self) -> bool:
        return self.peek_token and self.peek_token.type in {
            TokenType.EQ, TokenType.PLUS_EQ, TokenType.MINUS_EQ, TokenType.MUL_EQ, TokenType.DIV_EQ
        }

    # ---- top-level ----
    def parse_program(self) -> A.Program:
        program = A.Program()
        while self.current_token.type != TokenType.EOF:
            stmt = self._parse_statement()
            if stmt is not None:
                program.statements.append(stmt)
            self._next_token()
        return program

    # ---- statements ----
    def _parse_statement(self) -> Optional[A.Statement]:
        # assignment: ident <op>= ...
        if self.current_token.type == TokenType.IDENT and self._peek_assignment_op():
            return self._parse_assignment_statement()

        ct = self.current_token.type
        match ct:
            case TokenType.LET:
                return self._parse_let_statement()
            case TokenType.FN:
                return self._parse_function_statement()
            case TokenType.RETURN:
                return self._parse_return_statement()
            case TokenType.IF:
                return self._parse_if_statement()
            case TokenType.WHILE:
                return self._parse_while_statement()
            case TokenType.FOR:
                return self._parse_for_statement()
            case TokenType.CONTINUE:
                return self._parse_continue_statement()
            case TokenType.BREAK:
                return self._parse_break_statement()
            case _:
                return self._parse_expression_statement()

    def _parse_expression_statement(self) -> Optional[A.ExpressionStatement]:
        expr = self._parse_expression(Precedence.LOWEST)
        if expr is None:
            return None
        if self._peek_is(TokenType.SEMICOLON):
            self._next_token()
        return A.ExpressionStatement(expr=expr)

    def _parse_assignment_statement(self) -> A.AssignStatement:
        ident = A.IdentifierLiteral(value=self.current_token.literal)
        self._next_token()  # move to assignment operator
        if self.current_token.type not in {TokenType.EQ, TokenType.PLUS_EQ, TokenType.MINUS_EQ, TokenType.MUL_EQ, TokenType.DIV_EQ}:
            self.errors.append(f"Invalid assignment operator {self.current_token.literal} at line {self.current_token.line_no}")
        operator = self.current_token.literal
        self._next_token()  # move to rhs
        rhs = self._parse_expression(Precedence.LOWEST)
        if not self._expect_peek(TokenType.SEMICOLON):
            self._peek_error(TokenType.SEMICOLON)
        return A.AssignStatement(ident=ident, operator=operator, right_value=rhs)

    def _parse_let_statement(self) -> Optional[A.LetStatement]:
        stmt = A.LetStatement()
        if not self._expect_peek(TokenType.IDENT):
            self._peek_error(TokenType.IDENT)
            return None
        stmt.name = A.IdentifierLiteral(value=self.current_token.literal)

        if not self._expect_peek(TokenType.COLON):
            self._peek_error(TokenType.COLON)
            return None
        if not self._expect_peek(TokenType.TYPE):
            self._peek_error(TokenType.TYPE)
            return None
        stmt.value_type = self.current_token.literal

        if not self._expect_peek(TokenType.EQ):
            self._peek_error(TokenType.EQ)
            return None
        # read expression
        self._next_token()
        stmt.value = self._parse_expression(Precedence.LOWEST)

        # consume semicolon(s)
        while not self._current_is(TokenType.SEMICOLON) and not self._current_is(TokenType.EOF):
            self._next_token()
        return stmt

    def _parse_function_statement(self) -> Optional[A.FunctionStatement]:
        stmt = A.FunctionStatement()
        if not self._expect_peek(TokenType.IDENT):
            return None
        stmt.name = A.IdentifierLiteral(value=self.current_token.literal)

        if not self._expect_peek(TokenType.LPAREN):
            return None
        stmt.parameters = self._parse_function_parameters()

        if not self._expect_peek(TokenType.ARROW):
            return None
        if not self._expect_peek(TokenType.TYPE):
            return None
        stmt.return_type = self.current_token.literal

        if not self._expect_peek(TokenType.LBRACE):
            return None
        stmt.body = self._parse_block_statement()
        return stmt

    def _parse_function_parameters(self) -> List[A.FunctionParameter]:
        params: List[A.FunctionParameter] = []
        if self._peek_is(TokenType.RPAREN):
            self._next_token()
            return params
        self._next_token()
        # first param
        if not self.current_token.literal:
            return params
        first = A.FunctionParameter(name=self.current_token.literal)
        if not self._expect_peek(TokenType.COLON):
            return params
        self._next_token()
        first.value_type = self.current_token.literal
        params.append(first)

        while self._peek_is(TokenType.COMMA):
            self._next_token()
            self._next_token()
            param = A.FunctionParameter(name=self.current_token.literal)
            if not self._expect_peek(TokenType.COLON):
                return params
            self._next_token()
            param.value_type = self.current_token.literal
            params.append(param)

        if not self._expect_peek(TokenType.RPAREN):
            return params
        return params

    def _parse_return_statement(self) -> Optional[A.ReturnStatement]:
        self._next_token()
        retval = self._parse_expression(Precedence.LOWEST)
        if not self._expect_peek(TokenType.SEMICOLON):
            self._peek_error(TokenType.SEMICOLON)
        return A.ReturnStatement(return_value=retval)

    def _parse_block_statement(self) -> A.BlockStatement:
        block = A.BlockStatement()
        self._next_token()
        while not self._current_is(TokenType.RBRACE) and not self._current_is(TokenType.EOF):
            stmt = self._parse_statement()
            if stmt is not None:
                block.statements.append(stmt)
            self._next_token()
        return block

    def _parse_if_statement(self) -> Optional[A.IfStatement]:
        # We're already on the IF token, parse the condition
        # Expect: if (condition) { consequence } [else { alternative }]
        if not self._expect_peek(TokenType.LPAREN):
            self._peek_error(TokenType.LPAREN)
            return None

        self._next_token()  # Move to first token of condition
        condition = self._parse_expression(Precedence.LOWEST)

        if not self._expect_peek(TokenType.RPAREN):
            self._peek_error(TokenType.RPAREN)
            return None

        if not self._expect_peek(TokenType.LBRACE):
            self._peek_error(TokenType.LBRACE)
            return None

        consequence = self._parse_block_statement()

        alternative = None
        if self._peek_is(TokenType.ELSE):
            self._next_token()  # consume ELSE
            if not self._expect_peek(TokenType.LBRACE):
                self._peek_error(TokenType.LBRACE)
                return None
            alternative = self._parse_block_statement()

        return A.IfStatement(
            condition=condition,
            consequence=consequence,
            alternative=alternative
        )

    def _parse_while_statement(self) -> Optional[A.WhileStatement]:
        self._next_token()
        cond = self._parse_expression(Precedence.LOWEST)
        if not self._expect_peek(TokenType.LBRACE):
            return None
        body = self._parse_block_statement()
        return A.WhileStatement(condition=cond, body=body)

    def _parse_for_statement(self) -> Optional[A.ForStatement]:
        # expects ( let ... ; <cond> ; <action> ) { ... }
        if not self._expect_peek(TokenType.LPAREN):
            return None
        if not self._expect_peek(TokenType.LET):
            return None
        var_decl = self._parse_let_statement()
        # condition
        if not self._peek_is(TokenType.SEMICOLON):
            self._next_token()
            cond = self._parse_expression(Precedence.LOWEST)
        else:
            cond = None
        if not self._expect_peek(TokenType.SEMICOLON):
            return None
        if not self._peek_is(TokenType.RPAREN):
            self._next_token()
            action = self._parse_expression(Precedence.LOWEST)
        else:
            action = None
        if not self._expect_peek(TokenType.RPAREN):
            return None
        if not self._expect_peek(TokenType.LBRACE):
            return None
        body = self._parse_block_statement()
        return A.ForStatement(var_declaration=var_decl, condition=cond, action=action, body=body)

    def _parse_break_statement(self) -> A.BreakStatement:
        self._next_token()
        return A.BreakStatement()

    def _parse_continue_statement(self) -> A.ContinueStatement:
        self._next_token()
        return A.ContinueStatement()

    # ---- expressions (Pratt) ----
    def _parse_expression(self, prec: Precedence) -> Optional[A.Expression]:
        prefix = self.prefix_parse_fns.get(self.current_token.type)
        if prefix is None:
            self.errors.append(f"No prefix parse function for {self.current_token}")
            return None

        left = prefix()
        # postfix ++/-- of the current node (e.g., ident++)
        if self._peek_is(TokenType.PLUS_PLUS) or self._peek_is(TokenType.MINUS_MINUS):
            self._next_token()
            left = self._parse_postfix_expression(left)

        while not self._peek_is(TokenType.SEMICOLON) and prec < self._peek_precedence():
            infix = self.infix_parse_fns.get(self.peek_token.type)
            if infix is None:
                break
            self._next_token()
            left = infix(left)
        return left

    def _parse_infix_expression(self, left: A.Expression) -> A.InfixExpression:
        node = A.InfixExpression(left_node=left, operator=self.current_token.literal)
        precedence = self._current_precedence()
        self._next_token()
        node.right_node = self._parse_expression(precedence)
        return node

    def _parse_grouped_expression(self) -> Optional[A.Expression]:
        self._next_token()
        expr = self._parse_expression(Precedence.LOWEST)
        if not self._expect_peek(TokenType.RPAREN):
            return None
        return expr

    def _parse_call_expression(self, function: A.Expression) -> A.CallExpression:
        node = A.CallExpression(function=function)
        node.arguments = self._parse_expression_list(TokenType.RPAREN)
        return node

    def _parse_expression_list(self, end: TokenType) -> List[A.Expression]:
        args: List[A.Expression] = []
        if self._peek_is(end):
            self._next_token()
            return args
        self._next_token()
        first = self._parse_expression(Precedence.LOWEST)
        if first is not None:
            args.append(first)
        while self._peek_is(TokenType.COMMA):
            self._next_token()
            self._next_token()
            arg = self._parse_expression(Precedence.LOWEST)
            if arg is not None:
                args.append(arg)
        if not self._expect_peek(end):
            return args
        return args

    def _parse_prefix_expression(self) -> A.PrefixExpression:
        node = A.PrefixExpression(operator=self.current_token.literal)
        self._next_token()
        node.right_node = self._parse_expression(Precedence.PREFIX)
        return node

    def _parse_postfix_expression(self, left: A.Expression) -> A.PostfixExpression:
        operator = self.current_token.literal
        return A.PostfixExpression(left_node=left, operator=operator)

    def _parse_assignment_expression(self, left: A.Expression) -> A.InfixExpression:
        # create an infix node representing assignment-like operators
        op = self.current_token.literal
        node = A.InfixExpression(left_node=left, operator=op)
        self._next_token()
        node.right_node = self._parse_expression(Precedence.LOWEST)
        return node

    # ---- prefix literal helpers ----
    def _parse_literal(self, cls, converter: Callable[[Any], Any]) -> Optional[A.Expression]:
        inst = cls()
        try:
            inst.value = converter(self.current_token.literal)
        except Exception:
            self.errors.append(f"Could not parse literal {self.current_token.literal} as {cls.__name__}")
            return None
        return inst

    def _parse_int_literal(self) -> Optional[A.IntegerLiteral]:
        return self._parse_literal(A.IntegerLiteral, int)

    def _parse_float_literal(self) -> Optional[A.FloatLiteral]:
        return self._parse_literal(A.FloatLiteral, float)

    def _parse_string_literal(self) -> Optional[A.StringLiteral]:
        return self._parse_literal(A.StringLiteral, lambda x: str(x))

    def _parse_identifier(self) -> A.IdentifierLiteral:
        return A.IdentifierLiteral(value=self.current_token.literal)

    def _parse_boolean(self) -> A.BooleanLiteral:
        # FIXED: produce real Python bool values
        val = self.current_token.type == TokenType.TRUE
        return A.BooleanLiteral(value=val)
