from __future__ import annotations
from typing import Callable, Dict, Optional, List, Any
from enum import IntEnum, auto

from frontend.lexer import Lexer
from frontend.token import TokenType, Token
from frontend import ast as A
from frontend.ast import SourceLocation
from util.errors import ErrorCollector
from util.diagnostics import DiagnosticEngine


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
    TokenType.LBRACKET: Precedence.INDEX,
    TokenType.DOT: Precedence.INDEX,

    TokenType.PLUS_PLUS: Precedence.INDEX,
    TokenType.MINUS_MINUS: Precedence.INDEX,
}


class Parser:
    """
    Pratt/Top-down operator precedence parser for Similang. Produces AST nodes from frontend.ast.
    Collects errors in self.errors (does not raise).
    """

    def __init__(self, lexer: Lexer, *, diag: Optional[DiagnosticEngine] = None) -> None:
        self.lexer = lexer
        self.error_collector = ErrorCollector(diag=diag)
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
            TokenType.LBRACKET: self._parse_array_literal,
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
        self.infix_parse_fns[TokenType.LBRACKET] = self._parse_index_expression
        self.infix_parse_fns[TokenType.DOT] = self._parse_field_access_expression

        # prime tokens
        self._next_token()
        self._next_token()

    @property
    def errors(self) -> list:
        """Backward-compatible access to collected error messages."""
        return [e.format() for e in self.error_collector.errors]

    # ---- location helpers ----
    def _loc(self, token: Token | None = None) -> SourceLocation:
        """Build a SourceLocation from a token (defaults to current_token)."""
        tok = token or self.current_token
        if tok is None:
            return SourceLocation()
        return SourceLocation(line=tok.line_no, col=tok.col)

    def _tag(self, node: A.Node, token: Token | None = None) -> A.Node:
        """Attach source location to *node* and return it for chaining."""
        node.loc = self._loc(token)
        return node

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
        # index assignment: ident[expr] = expr;
        # field assignment: ident.field = expr;
        if self.current_token.type == TokenType.IDENT:
            if self._peek_is(TokenType.LBRACKET):
                return self._try_parse_index_assign_or_expr()
            if self._peek_is(TokenType.DOT):
                return self._try_parse_field_assign_or_expr()
            if self._peek_assignment_op():
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
            case TokenType.STRUCT:
                return self._parse_struct_definition()
            case _:
                return self._parse_expression_statement()

    def _parse_expression_statement(self) -> Optional[A.ExpressionStatement]:
        start = self.current_token
        expr = self._parse_expression(Precedence.LOWEST)
        if expr is None:
            return None
        if self._peek_is(TokenType.SEMICOLON):
            self._next_token()
        node = A.ExpressionStatement(expr=expr)
        self._tag(node, start)
        return node

    def _parse_assignment_statement(self, expect_semi: bool = True) -> A.AssignStatement:
        start = self.current_token
        ident = A.IdentifierLiteral(value=self.current_token.literal)
        self._tag(ident)
        self._next_token()  # move to assignment operator
        if self.current_token.type not in {TokenType.EQ, TokenType.PLUS_EQ, TokenType.MINUS_EQ, TokenType.MUL_EQ, TokenType.DIV_EQ}:
            self.error_collector.add_error(f"Invalid assignment operator {self.current_token.literal}", line=self.current_token.line_no)
        operator = self.current_token.literal
        self._next_token()  # move to rhs
        rhs = self._parse_expression(Precedence.LOWEST)
        if expect_semi:
            if not self._expect_peek(TokenType.SEMICOLON):
                self._peek_error(TokenType.SEMICOLON)
        node = A.AssignStatement(ident=ident, operator=operator, right_value=rhs)
        self._tag(node, start)
        return node

    def _parse_let_statement(self) -> Optional[A.LetStatement]:
        start = self.current_token
        stmt = A.LetStatement()
        self._tag(stmt, start)
        if not self._expect_peek(TokenType.IDENT):
            self._peek_error(TokenType.IDENT)
            return None
        stmt.name = A.IdentifierLiteral(value=self.current_token.literal)
        self._tag(stmt.name)

        if not self._expect_peek(TokenType.COLON):
            self._peek_error(TokenType.COLON)
            return None

        # Parse type annotation: plain TYPE, [size]TYPE for arrays, or IDENT for struct types
        stmt.value_type = self._parse_type_annotation()
        if stmt.value_type is None:
            return None

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
        start = self.current_token
        stmt = A.FunctionStatement()
        self._tag(stmt, start)
        if not self._expect_peek(TokenType.IDENT):
            return None
        stmt.name = A.IdentifierLiteral(value=self.current_token.literal)
        self._tag(stmt.name)

        if not self._expect_peek(TokenType.LPAREN):
            return None
        stmt.parameters = self._parse_function_parameters()

        if not self._expect_peek(TokenType.ARROW):
            return None
        # Parse return type (could be TYPE, IDENT for structs, or [size]TYPE for arrays)
        ret_type = self._parse_type_annotation()
        if ret_type is None:
            return None
        stmt.return_type = ret_type

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
        self._tag(first)
        if not self._expect_peek(TokenType.COLON):
            return params
        first.value_type = self._parse_type_annotation()
        params.append(first)

        while self._peek_is(TokenType.COMMA):
            self._next_token()
            self._next_token()
            param = A.FunctionParameter(name=self.current_token.literal)
            self._tag(param)
            if not self._expect_peek(TokenType.COLON):
                return params
            param.value_type = self._parse_type_annotation()
            params.append(param)

        if not self._expect_peek(TokenType.RPAREN):
            return params
        return params

    def _parse_return_statement(self) -> Optional[A.ReturnStatement]:
        start = self.current_token
        self._next_token()
        retval = self._parse_expression(Precedence.LOWEST)
        if not self._expect_peek(TokenType.SEMICOLON):
            self._peek_error(TokenType.SEMICOLON)
        node = A.ReturnStatement(return_value=retval)
        self._tag(node, start)
        return node

    def _parse_block_statement(self) -> A.BlockStatement:
        block = A.BlockStatement()
        self._tag(block)
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
        start_tok = self.current_token
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

        node = A.IfStatement(
            condition=condition,
            consequence=consequence,
            alternative=alternative
        )
        self._tag(node, start_tok)
        return node

    def _parse_while_statement(self) -> Optional[A.WhileStatement]:
        start = self.current_token
        self._next_token()
        cond = self._parse_expression(Precedence.LOWEST)
        if not self._expect_peek(TokenType.LBRACE):
            return None
        body = self._parse_block_statement()
        node = A.WhileStatement(condition=cond, body=body)
        self._tag(node, start)
        return node

    def _parse_for_statement(self) -> Optional[A.ForStatement]:
        # expects ( let ... ; <cond> ; <action> ) { ... }
        start = self.current_token
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
            # Detect compound/simple assignment: ident (=|+=|-=|*=|/=) expr
            if (self.current_token.type == TokenType.IDENT
                    and self.peek_token
                    and self.peek_token.type in {
                        TokenType.EQ, TokenType.PLUS_EQ, TokenType.MINUS_EQ,
                        TokenType.MUL_EQ, TokenType.DIV_EQ}):
                action = self._parse_assignment_statement(expect_semi=False)
            else:
                action = self._parse_expression(Precedence.LOWEST)
        else:
            action = None
        if not self._expect_peek(TokenType.RPAREN):
            return None
        if not self._expect_peek(TokenType.LBRACE):
            return None
        body = self._parse_block_statement()
        node = A.ForStatement(var_declaration=var_decl, condition=cond, action=action, body=body)
        self._tag(node, start)
        return node

    def _parse_break_statement(self) -> A.BreakStatement:
        start = self.current_token
        self._next_token()
        node = A.BreakStatement()
        self._tag(node, start)
        return node

    def _parse_continue_statement(self) -> A.ContinueStatement:
        start = self.current_token
        self._next_token()
        node = A.ContinueStatement()
        self._tag(node, start)
        return node

    # ---- expressions (Pratt) ----
    def _parse_expression(self, prec: Precedence) -> Optional[A.Expression]:
        prefix = self.prefix_parse_fns.get(self.current_token.type)
        if prefix is None:
            self.error_collector.add_error(f"No prefix parse function for {self.current_token}",
                                              line=self.current_token.line_no if self.current_token else None)
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
        self._tag(node)
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
        self._tag(node)  # tag at the '(' token
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
        self._tag(node)
        self._next_token()
        node.right_node = self._parse_expression(Precedence.PREFIX)
        return node

    def _parse_postfix_expression(self, left: A.Expression) -> A.PostfixExpression:
        operator = self.current_token.literal
        node = A.PostfixExpression(left_node=left, operator=operator)
        self._tag(node)
        return node

    def _parse_assignment_expression(self, left: A.Expression) -> A.InfixExpression:
        # create an infix node representing assignment-like operators
        op = self.current_token.literal
        node = A.InfixExpression(left_node=left, operator=op)
        self._tag(node)
        self._next_token()
        node.right_node = self._parse_expression(Precedence.LOWEST)
        return node

    # ---- type annotation parsing ----
    def _parse_type_annotation(self) -> Optional[str]:
        """Parse a type annotation after a colon or arrow.

        Supports:
          - Built-in types: int, float, bool, str, void, ...
          - User-defined struct types (identifiers): Point, MyStruct
          - Array types: [5]int, [10]Point
        """
        # Array type: [size]element_type
        if self._peek_is(TokenType.LBRACKET):
            self._next_token()  # consume [
            if not self._expect_peek(TokenType.INT):
                self.error_collector.add_error("Expected array size (integer) in type annotation",
                                               line=self.current_token.line_no)
                return None
            size = int(self.current_token.literal)
            if not self._expect_peek(TokenType.RBRACKET):
                return None
            # element type follows the bracket
            if self._peek_is(TokenType.TYPE):
                self._next_token()
                elem_type = self.current_token.literal
            elif self._peek_is(TokenType.IDENT):
                self._next_token()
                elem_type = self.current_token.literal
            else:
                self.error_collector.add_error("Expected element type after array size",
                                               line=self.current_token.line_no)
                return None
            return f"[{size}]{elem_type}"

        # Plain TYPE keyword
        if self._peek_is(TokenType.TYPE):
            self._next_token()
            return self.current_token.literal

        # User-defined type (struct name) — an IDENT
        if self._peek_is(TokenType.IDENT):
            self._next_token()
            return self.current_token.literal

        self._peek_error(TokenType.TYPE)
        return None

    # ---- struct definition ----
    def _parse_struct_definition(self) -> Optional[A.StructDefinition]:
        """Parse: struct Name { field1: type1, field2: type2 }"""
        start = self.current_token
        if not self._expect_peek(TokenType.IDENT):
            return None
        name = A.IdentifierLiteral(value=self.current_token.literal)
        self._tag(name)

        if not self._expect_peek(TokenType.LBRACE):
            return None

        fields: List[A.StructField] = []
        # parse fields: name: type, ...
        while not self._peek_is(TokenType.RBRACE) and not self._peek_is(TokenType.EOF):
            self._next_token()  # move to field name
            if self.current_token.type != TokenType.IDENT:
                self.error_collector.add_error(
                    f"Expected field name in struct definition, got {self.current_token.type}",
                    line=self.current_token.line_no)
                return None
            field_name = self.current_token.literal
            if not self._expect_peek(TokenType.COLON):
                return None
            field_type = self._parse_type_annotation()
            if field_type is None:
                return None
            f = A.StructField(name=field_name, value_type=field_type)
            self._tag(f)
            fields.append(f)
            # optional trailing comma
            if self._peek_is(TokenType.COMMA):
                self._next_token()

        if not self._expect_peek(TokenType.RBRACE):
            return None

        node = A.StructDefinition(name=name, fields=fields)
        self._tag(node, start)
        return node

    # ---- array literal ----
    def _parse_array_literal(self) -> Optional[A.ArrayLiteral]:
        """Parse: [expr1, expr2, ...]"""
        start = self.current_token
        elements = self._parse_expression_list(TokenType.RBRACKET)
        node = A.ArrayLiteral(elements=elements)
        self._tag(node, start)
        return node

    # ---- index expression ----
    def _parse_index_expression(self, left: A.Expression) -> A.IndexExpression:
        """Parse: left[index]"""
        node = A.IndexExpression(left=left)
        self._tag(node)
        self._next_token()  # move past [
        node.index = self._parse_expression(Precedence.LOWEST)
        if not self._expect_peek(TokenType.RBRACKET):
            pass  # error already recorded
        return node

    # ---- field access expression ----
    def _parse_field_access_expression(self, left: A.Expression) -> A.Expression:
        """Parse: left.field_name

        If followed by '{', this is a struct literal: StructName { ... }
        """
        # Regular field access: left.field
        self._next_token()  # move past .
        if self.current_token.type != TokenType.IDENT:
            self.error_collector.add_error(
                f"Expected field name after '.', got {self.current_token.type}",
                line=self.current_token.line_no)
            return left
        field_name = self.current_token.literal
        node = A.FieldAccessExpression(object=left, field_name=field_name)
        self._tag(node)
        return node

    # ---- struct literal ----
    def _parse_struct_literal(self, struct_name: str) -> Optional[A.StructLiteral]:
        """Parse: StructName { field1: expr1, field2: expr2 }
        Called when we've seen IDENT followed by '{'.
        """
        start = self.current_token
        # current_token is '{' — already consumed
        field_values: List[tuple] = []

        while not self._peek_is(TokenType.RBRACE) and not self._peek_is(TokenType.EOF):
            self._next_token()  # move to field name
            if self.current_token.type != TokenType.IDENT:
                self.error_collector.add_error(
                    f"Expected field name in struct literal, got {self.current_token.type}",
                    line=self.current_token.line_no)
                return None
            fname = self.current_token.literal
            if not self._expect_peek(TokenType.COLON):
                return None
            self._next_token()
            val = self._parse_expression(Precedence.LOWEST)
            if val is None:
                return None
            field_values.append((fname, val))
            if self._peek_is(TokenType.COMMA):
                self._next_token()

        if not self._expect_peek(TokenType.RBRACE):
            return None

        node = A.StructLiteral(struct_name=struct_name, field_values=field_values)
        self._tag(node, start)
        return node

    # ---- index / field assignment helpers ----
    def _try_parse_index_assign_or_expr(self) -> Optional[A.Statement]:
        """When we see ident[ — it could be index assignment or expression."""
        start = self.current_token
        ident = A.IdentifierLiteral(value=self.current_token.literal)
        self._tag(ident)
        self._next_token()  # move to [
        self._next_token()  # move past [
        index_expr = self._parse_expression(Precedence.LOWEST)
        if not self._expect_peek(TokenType.RBRACKET):
            pass

        # Check if this is an assignment: ident[idx] = expr;
        if self._peek_is(TokenType.EQ):
            self._next_token()  # consume =
            self._next_token()  # move to value
            val = self._parse_expression(Precedence.LOWEST)
            if self._peek_is(TokenType.SEMICOLON):
                self._next_token()
            node = A.IndexAssignStatement(array=ident, index=index_expr, value=val)
            self._tag(node, start)
            return node

        # Otherwise treat as expression statement (e.g., arr[0] as part of larger expression)
        idx_node = A.IndexExpression(left=ident, index=index_expr)
        self._tag(idx_node, start)
        # Continue parsing as expression (there might be more operators)
        left = idx_node
        while not self._peek_is(TokenType.SEMICOLON) and Precedence.LOWEST < self._peek_precedence():
            infix = self.infix_parse_fns.get(self.peek_token.type)
            if infix is None:
                break
            self._next_token()
            left = infix(left)
        if self._peek_is(TokenType.SEMICOLON):
            self._next_token()
        node = A.ExpressionStatement(expr=left)
        self._tag(node, start)
        return node

    def _try_parse_field_assign_or_expr(self) -> Optional[A.Statement]:
        """When we see ident. — it could be field assignment or expression."""
        start = self.current_token
        ident = A.IdentifierLiteral(value=self.current_token.literal)
        self._tag(ident)
        self._next_token()  # move to .
        self._next_token()  # move past . to field name
        if self.current_token.type != TokenType.IDENT:
            self.error_collector.add_error(
                f"Expected field name after '.', got {self.current_token.type}",
                line=self.current_token.line_no)
            return None
        field_name = self.current_token.literal

        # Check if this is an assignment: ident.field = expr;
        if self._peek_is(TokenType.EQ):
            self._next_token()  # consume =
            self._next_token()  # move to value
            val = self._parse_expression(Precedence.LOWEST)
            if self._peek_is(TokenType.SEMICOLON):
                self._next_token()
            node = A.FieldAssignStatement(object=ident, field_name=field_name, value=val)
            self._tag(node, start)
            return node

        # Otherwise it's a field access expression
        field_node = A.FieldAccessExpression(object=ident, field_name=field_name)
        self._tag(field_node, start)
        left = field_node
        while not self._peek_is(TokenType.SEMICOLON) and Precedence.LOWEST < self._peek_precedence():
            infix = self.infix_parse_fns.get(self.peek_token.type)
            if infix is None:
                break
            self._next_token()
            left = infix(left)
        if self._peek_is(TokenType.SEMICOLON):
            self._next_token()
        node = A.ExpressionStatement(expr=left)
        self._tag(node, start)
        return node

    # ---- prefix literal helpers ----
    def _parse_literal(self, cls, converter: Callable[[Any], Any]) -> Optional[A.Expression]:
        inst = cls()
        try:
            inst.value = converter(self.current_token.literal)
        except Exception:
            self.error_collector.add_error(f"Could not parse literal {self.current_token.literal} as {cls.__name__}",
                                              line=self.current_token.line_no if self.current_token else None)
            return None
        self._tag(inst)
        return inst

    def _parse_int_literal(self) -> Optional[A.IntegerLiteral]:
        return self._parse_literal(A.IntegerLiteral, int)

    def _parse_float_literal(self) -> Optional[A.FloatLiteral]:
        return self._parse_literal(A.FloatLiteral, float)

    def _parse_string_literal(self) -> Optional[A.StringLiteral]:
        return self._parse_literal(A.StringLiteral, lambda x: str(x))

    def _parse_identifier(self) -> Optional[A.Expression]:
        name = self.current_token.literal
        node = A.IdentifierLiteral(value=name)
        self._tag(node)
        # Check for struct literal: Name { field: val, ... }
        if self._peek_is(TokenType.LBRACE):
            self._next_token()  # consume the {
            return self._parse_struct_literal(name)
        return node

    def _parse_boolean(self) -> A.BooleanLiteral:
        # FIXED: produce real Python bool values
        val = self.current_token.type == TokenType.TRUE
        node = A.BooleanLiteral(value=val)
        self._tag(node)
        return node
