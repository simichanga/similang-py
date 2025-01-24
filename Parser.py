from Lexer import Lexer
from Token import TokenType, Token
from typing import Callable
from enum import Enum, auto

from __imports__ import *

# Precedence Types
class PrecedenceType(Enum):
    P_LOWEST = 0
    P_EQUALS = auto()
    P_LESSGREATER = auto()
    P_SUM = auto()
    P_PRODUCT = auto()
    P_EXPONENT = auto()
    P_PREFIX = auto()
    P_CALL = auto()
    P_INDEX = auto()

# Predecence Mapping
PRECEDENCES : dict[TokenType, PrecedenceType] = {
    TokenType.PLUS: PrecedenceType.P_SUM,
    TokenType.MINUS: PrecedenceType.P_SUM,
    TokenType.SLASH: PrecedenceType.P_PRODUCT,
    TokenType.ASTERISK: PrecedenceType.P_PRODUCT,
    TokenType.MODULUS: PrecedenceType.P_PRODUCT,
    TokenType.POW: PrecedenceType.P_EXPONENT,

    TokenType.EQ_EQ: PrecedenceType.P_EQUALS,
    TokenType.NOT_EQ: PrecedenceType.P_EQUALS,
    TokenType.LT: PrecedenceType.P_LESSGREATER,
    TokenType.GT: PrecedenceType.P_LESSGREATER,
    TokenType.LT_EQ: PrecedenceType.P_LESSGREATER,
    TokenType.GT_EQ: PrecedenceType.P_LESSGREATER,

    TokenType.LPAREN: PrecedenceType.P_CALL,

    TokenType.PLUS_PLUS: PrecedenceType.P_INDEX,
    TokenType.MINUS_MINUS: PrecedenceType.P_INDEX,
}

class Parser:
    def __init__(self, lexer: Lexer) -> None:
        self.lexer: Lexer = lexer

        self.errors: list[str] = []

        self.current_token: Token | None = None
        self.peek_token: Token | None = None

        self.prefix_parse_fns: dict[TokenType, Callable] = {
            TokenType.IDENT: self.__parse_identifier,
            TokenType.INT: self.__parse_int_literal,
            TokenType.FLOAT: self.__parse_float_literal,
            TokenType.LPAREN: self.__parse_grouped_expression,
            TokenType.IF: self.__parse_if_statement,
            TokenType.TRUE: self.__parse_boolean,
            TokenType.FALSE: self.__parse_boolean,
            TokenType.STRING: self.__parse_string_literal,
            TokenType.MINUS: self.__parse_prefix_expression,
            TokenType.BANG: self.__parse_prefix_expression,
        }

        # Create a base dictionary with default values for all TokenTypes
        self.infix_parse_fns: dict[TokenType, Callable] = { tt: self.__parse_infix_expression for tt in TokenType }

        # Override specific cases explicitly
        self.infix_parse_fns[TokenType.LPAREN] = self.__parse_call_expression
        self.infix_parse_fns[TokenType.PLUS_PLUS] = self.__parse_postfix_expression
        self.infix_parse_fns[TokenType.MINUS_MINUS] = self.__parse_postfix_expression

        self.__next_token()
        self.__next_token()

    # region Parser Helpers
    def __next_token(self) -> None:
        self.current_token = self.peek_token
        self.peek_token = self.lexer.next_token()

    def __current_token_is(self, tt: TokenType) -> bool:
        return self.current_token.type == tt 

    def __peek_token_is(self, tt: TokenType) -> bool:
        return self.peek_token.type == tt

    def __peek_token_is_assignment(self) -> bool:
        assignment_operators: list[TokenType] = [
            TokenType.EQ,
            TokenType.PLUS_EQ,
            TokenType.MINUS_EQ,
            TokenType.MUL_EQ,
            TokenType.DIV_EQ,
        ]
        return self.peek_token.type in assignment_operators

    def __expect_peek(self, tt: TokenType) -> bool:
        if self.__peek_token_is(tt):
            self.__next_token()
            return True
        else:
            self.__peek_error(tt)
            return False

    def __current_precedence(self) -> PrecedenceType:
        prec: int | None = PRECEDENCES.get(self.current_token.type)
        return prec or PrecedenceType.P_LOWEST

    def __peek_precedence(self) -> PrecedenceType:
        prec: int | None = PRECEDENCES.get(self.peek_token.type)
        return prec or PrecedenceType.P_LOWEST

    def __peek_error(self, tt: TokenType) -> None:
        self.errors.append(f'Expected next token to be {tt}, got {self.peek_token.type} instead.')

    def __no_prefix_parse_fn_error(self, tt: TokenType) -> None:
        self.errors.append(f'No Prefix Parse Function for {tt} found.')
    # endregion

    def parse_program(self) -> Program:
        program: Program = Program()

        while self.current_token.type != TokenType.EOF:
            stmt: Statement = self.__parse_statement()
            if stmt is not None:
                program.statements.append(stmt)
            self.__next_token()

        return program

    # region Statement Methods
    def __parse_statement(self) -> Statement:
        if self.current_token.type == TokenType.IDENT and self.__peek_token_is_assignment():
            return self.__parse_assignment_statement()

        # TODO refactor this, it's utterly retarded
        match self.current_token.type:
            case TokenType.LET:
                return self.__parse_let_statement()
            case TokenType.FN:
                return self.__parse_function_statement()
            case TokenType.RETURN:
                return self.__parse_return_statement()
            case TokenType.WHILE:
                return self.__parse_while_statement()
            case TokenType.FOR:
                return self.__parse_for_statement()
            case TokenType.CONTINUE:
                return self.__parse_continue_statement()
            case TokenType.BREAK:
                return self.__parse_break_statement()
            case _:
                return self.__parse_expression_statement()

    def __parse_expression_statement(self) -> ExpressionStatement | None:
        expr = self.__parse_expression(PrecedenceType.P_LOWEST)
        if expr is None:
            return None

        if self.__peek_token_is(TokenType.SEMICOLON):
            self.__next_token()
        
        return ExpressionStatement(expr=expr)

    # TODO refactor this so it has proper error checking
    def __parse_let_statement(self) -> LetStatement:
        # let a: int = 10;
        stmt: LetStatement = LetStatement()

        if not self.__expect_peek(TokenType.IDENT):
            raise SyntaxError(f'Expected identifier')

        stmt.name = IdentifierLiteral(value = self.current_token.literal)

        # Syntax Checking
        if not self.__expect_peek(TokenType.COLON):
            raise SyntaxError(f'Variable expects colon.')

        if not self.__expect_peek(TokenType.TYPE):
            raise SyntaxError(f'Variable expects type.')

        stmt.value_type = self.current_token.literal

        if not self.__expect_peek(TokenType.EQ):
            raise SyntaxError(f'Variable expects initialization on creation.')

        self.__next_token()

        stmt.value = self.__parse_expression(PrecedenceType.P_LOWEST)

        while not self.__current_token_is(TokenType.SEMICOLON) and not self.__current_token_is(TokenType.EOF):
            self.__next_token()

        return stmt

    def __parse_function_statement(self) -> FunctionStatement | None:
        stmt: FunctionStatement = FunctionStatement()

        if not self.__expect_peek(TokenType.IDENT):
            return None

        stmt.name = IdentifierLiteral(value = self.current_token.literal)

        if not self.__expect_peek(TokenType.LPAREN):
            return None

        stmt.parameters = self.__parse_function_parameters()

        if not self.__expect_peek(TokenType.ARROW):
            return None

        if not self.__expect_peek(TokenType.TYPE):
            return None

        stmt.return_type = self.current_token.literal

        if not self.__expect_peek(TokenType.LBRACE):
            return None

        stmt.body = self.__parse_block_statement()

        return stmt

    def __parse_function_parameters(self) -> list[FunctionParameter] | None:
        params: list[FunctionParameter] = []

        if self.__peek_token_is(TokenType.RPAREN):
            self.__next_token()
            return params

        self.__next_token()

        # TODO refactor this retarded code
        # read first param
        first_param: FunctionParameter = FunctionParameter(name = self.current_token.literal)

        if not self.__expect_peek(TokenType.COLON):
            return None

        self.__next_token()

        first_param.value_type = self.current_token.literal
        params.append(first_param)

        while self.__peek_token_is(TokenType.COMMA):
            self.__next_token()
            self.__next_token()

            # read from the second param onwards
            param: FunctionParameter = FunctionParameter(name = self.current_token.literal)

            if not self.__expect_peek(TokenType.COLON):
                return None

            self.__next_token()

            param.value_type = self.current_token.literal
            params.append(param)

        if not self.__expect_peek(TokenType.RPAREN):
            return None

        return params 

    def __parse_return_statement(self) -> ReturnStatement | None:
        self.__next_token()

        return_value = self.__parse_expression(PrecedenceType.P_LOWEST)

        if not self.__expect_peek(TokenType.SEMICOLON):
            return None

        return ReturnStatement(return_value = return_value)

    def __parse_block_statement(self) -> BlockStatement:
        block_stmt: BlockStatement = BlockStatement()

        self.__next_token()

        while not self.__current_token_is(TokenType.RBRACE) and not self.__current_token_is(TokenType.EOF):
            stmt: Statement = self.__parse_statement()
            if stmt is not None:
                block_stmt.statements.append(stmt)

            self.__next_token()

        return block_stmt

    def __parse_assignment_statement(self) -> AssignStatement:
    # Ensure the left-hand side is an identifier
        ident = IdentifierLiteral(value=self.current_token.literal)

        self.__next_token()  # Advance to the operator token

        # Validate that the current token is a valid assignment operator
        assignment_operators = {
            TokenType.EQ, TokenType.PLUS_EQ, TokenType.MINUS_EQ,
            TokenType.MUL_EQ, TokenType.DIV_EQ,
        }
        if self.current_token.type not in assignment_operators:
            raise SyntaxError(
                f"Invalid assignment operator '{self.current_token.literal}' "
                f"at line {self.current_token.line_no}."
            )

        operator = self.current_token.literal
        self.__next_token()  # Advance to the right-hand side expression

        # Parse the right-hand side expression
        right_value = self.__parse_expression(PrecedenceType.P_LOWEST)

        # print(f'Debug Assign Statement: {ident=}, {operator=}, {right_value}')
        # print(f'Current Token: {self.current_token}')

        # Ensure the statement ends with a semicolon
        # if not self.__current_token_is(TokenType.SEMICOLON):
        #     raise SyntaxError(
        #         f"Expected ';' after assignment statement, got '{self.current_token.literal}' "
        #         f"at line {self.current_token.line_no}."
        #     )

        # Construct and return the assignment statement
        return AssignStatement(ident=ident, operator=operator, right_value=right_value)

    def __parse_if_statement(self) -> IfStatement:
        condition: Expression = None
        consequence: BlockStatement = None
        alternative: BlockStatement = None

        self.__next_token()

        condition = self.__parse_expression(PrecedenceType.P_LOWEST)

        if not self.__expect_peek(TokenType.LBRACE):
            return None

        consequence = self.__parse_block_statement()

        if self.__peek_token_is(TokenType.ELSE):
            self.__next_token()

            if not self.__expect_peek(TokenType.LBRACE):
                return None

            alternative = self.__parse_block_statement()

        return IfStatement(condition, consequence, alternative)

    def __parse_while_statement(self) -> WhileStatement:
        condition: Expression = None
        body: BlockStatement = None

        self.__next_token()

        condition = self.__parse_expression(PrecedenceType.P_LOWEST)

        if not self.__expect_peek(TokenType.LBRACE):
            return None

        body = self.__parse_block_statement()

        return WhileStatement(condition = condition, body = body)

    def __parse_for_statement(self) -> ForStatement:
        # Parse variable declaration
        self.__expect_peek(TokenType.LPAREN)

        self.__expect_peek(TokenType.LET)
        var_declaration = self.__parse_let_statement()
        # CHECKPOINT ALL GOOD UNTIL NOW

        # Parse condition
        # TODO fix this, it nulls out the condition
        if not self.__peek_token_is(TokenType.SEMICOLON):
            self.__next_token()
            condition = self.__parse_expression(PrecedenceType.P_LOWEST)
        else:
            condition = None

        # Parse action
        self.__next_token()
        self.__next_token()

        action = self.__parse_assignment_statement()  # Ensure this handles `AssignStatement` or `InfixExpression`

        # Parse body
        self.__expect_peek(TokenType.LBRACE)
        body = self.__parse_block_statement()

        return ForStatement(
            var_declaration=var_declaration,
            condition=condition,
            action=action,
            body=body,
        )

    def __parse_break_statement(self) -> BreakStatement:
        self.__next_token()
        return BreakStatement()

    def __parse_continue_statement(self) -> ContinueStatement:
        self.__next_token()
        return ContinueStatement()
    # endregion

    # region Expression Methods
    def __parse_expression(self, precedence: PrecedenceType) -> None:
        prefix_fn: Callable | None = self.prefix_parse_fns.get(self.current_token.type)
        if prefix_fn is None:
            self.__no_prefix_parse_fn_error(self.current_token.type)
            return None

        left_expr: Expression = prefix_fn()
        while not self.__peek_token_is(TokenType.SEMICOLON) and precedence.value < self.__peek_precedence().value:
            infix_fn: Callable | None = self.infix_parse_fns.get(self.peek_token.type)
            if infix_fn is None:
                return left_expr

            self.__next_token()

            left_expr = infix_fn(left_expr)

        return left_expr

    def __parse_infix_expression(self, left_node: Expression) -> Expression:
        infix_expr: InfixExpression = InfixExpression(left_node = left_node, operator = self.current_token.literal)

        precedence = self.__current_precedence()

        self.__next_token()

        infix_expr.right_node = self.__parse_expression(precedence)

        return infix_expr

    def __parse_grouped_expression(self) -> Expression:
        self.__next_token()

        expr: Expression = self.__parse_expression(PrecedenceType.P_LOWEST)

        if not self.__expect_peek(TokenType.RPAREN):
            return None

        return expr

    def __parse_call_expression(self, function: Expression) -> CallExpression:
        expr: CallExpression = CallExpression(function = function)
        expr.arguments = self.__parse_expression_list(TokenType.RPAREN)

        return expr

    def __parse_expression_list(self, end: TokenType) -> list[Expression]:
        e_list: list[Expression] = []

        if self.__peek_token_is(end):
            self.__next_token()
            return e_list

        self.__next_token()

        e_list.append(self.__parse_expression(PrecedenceType.P_LOWEST))

        while self.__peek_token_is(TokenType.COMMA):
            self.__next_token()
            self.__next_token()

            e_list.append(self.__parse_expression(PrecedenceType.P_LOWEST))

        if not self.__expect_peek(end):
            return None

        return e_list

    def __parse_prefix_expression(self) -> PrefixExpression:
        prefix_expr: PrefixExpression = PrefixExpression(operator = self.current_token.literal)

        self.__next_token()

        prefix_expr.right_node = self.__parse_expression(PrecedenceType.P_PREFIX)

        return prefix_expr

    def __parse_postfix_expression(self, left_node: Expression) -> PostfixExpression:
        return PostfixExpression(left_node = left_node, operator = self.current_token.literal)
    # endregion

    # region Prefix Methods
    def __parse_identifier(self) -> IdentifierLiteral:
        return IdentifierLiteral(value = self.current_token.literal)

    def __parse_int_literal(self) -> Expression:
        int_lit: IntegerLiteral = IntegerLiteral()

        try:
            int_lit.value = int(self.current_token.literal)
        except:
            self.errors.append(f'Could not parse `{self.current_token.literal}` as an integer.')
            return None

        return int_lit

    def __parse_float_literal(self) -> Expression:
        float_lit: IntegerLiteral = FloatLiteral()

        try:
            float_lit.value = float(self.current_token.literal)
        except:
            self.errors.append(f'Could not parse `{self.current_token.literal}` as a float.')
            return None

        return float_lit

    def __parse_boolean(self) -> BooleanLiteral:
        return BooleanLiteral(value = self.__current_token_is(TokenType.TRUE))

    def __parse_string_literal(self) -> StringLiteral:
        return StringLiteral(value = self.current_token.literal)
    # endregion