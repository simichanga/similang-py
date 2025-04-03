from pipeline.lexer import Lexer
from pipeline.token import TokenType, Token
from typing import Callable, List, Union, Any, Set, Type
from enum import Enum, auto

from pipeline.ast import (
    Statement, Expression, Program,
    ExpressionStatement, LetStatement, FunctionStatement, ReturnStatement,
    BlockStatement, AssignStatement, IfStatement, WhileStatement, ForStatement,
    BreakStatement, ContinueStatement,
    InfixExpression, PrefixExpression, PostfixExpression, CallExpression,
    IntegerLiteral, FloatLiteral, IdentifierLiteral, BooleanLiteral, StringLiteral,
    FunctionParameter
)

from typing import Dict, Optional

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
PRECEDENCES : Dict[TokenType, PrecedenceType] = {
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
        self.current_token: Optional[Token] = None
        self.peek_token: Optional[Token] = None

        self.prefix_parse_fns: Dict[TokenType, Callable] = {
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
        self.infix_parse_fns: Dict[TokenType, Callable] = { tt: self.__parse_infix_expression for tt in TokenType }
        # Override specific cases explicitly
        self.infix_parse_fns[TokenType.LPAREN] = self.__parse_call_expression
        self.infix_parse_fns[TokenType.PLUS_PLUS] = self.__parse_postfix_expression
        self.infix_parse_fns[TokenType.MINUS_MINUS] = self.__parse_postfix_expression
        self.infix_parse_fns[TokenType.PLUS_EQ] = self.__parse_assignment_expression
        self.infix_parse_fns[TokenType.MINUS_EQ] = self.__parse_assignment_expression
        self.infix_parse_fns[TokenType.MUL_EQ] = self.__parse_assignment_expression
        self.infix_parse_fns[TokenType.DIV_EQ] = self.__parse_assignment_expression

        self.__next_token() # Initialize current_token
        self.__next_token() # Initialize peek_token

    # region Parser Helpers
    def __next_token(self) -> None:
        """Advance to the next token."""
        self.current_token = self.peek_token
        self.peek_token = self.lexer.next_token()

    def __current_token_is(self, tt: TokenType) -> bool:
        return self.current_token.type == tt

    def __peek_token_is(self, tt: TokenType) -> bool:
        return self.peek_token.type == tt

    def __peek_token_is_assignment(self) -> bool:
        assignment_operators: Set[TokenType] = {
            TokenType.EQ,
            TokenType.PLUS_EQ,
            TokenType.MINUS_EQ,
            TokenType.MUL_EQ,
            TokenType.DIV_EQ,
        }
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

    def __handle_parse_error(self, message: str) -> None:
        """Helper function: Handle parse errors and return None"""
        self.errors.append(f"Parse Error: {message}")  # TODO: can be replaced later with logging
        return None
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

    def __parse_assignment_expression(self, left_node: Expression) -> Expression:
        operator = self.current_token.literal
        self.__next_token()
        right_node = self.__parse_expression(PrecedenceType.P_LOWEST)

        return InfixExpression(left_node=left_node, operator=operator, right_node=right_node)

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

        # Check if an identifier exists
        if not self.__expect_peek(TokenType.IDENT):
            raise SyntaxError(f'Expected identifier at line {self.current_token.line_no}')

        stmt.name = IdentifierLiteral(value = self.current_token.literal)

        # Check if a colon exists
        if not self.__expect_peek(TokenType.COLON):
            raise SyntaxError(f'Variable expects colon at line {self.current_token.line_no}')

        # Check if a type declaration exists
        if not self.__expect_peek(TokenType.TYPE):
            raise SyntaxError(f'Variable expects type at line {self.current_token.line_no}')

        stmt.value_type = self.current_token.literal

        # Check if an equals sign exists
        if not self.__expect_peek(TokenType.EQ):
            raise SyntaxError(f'Variable expects initialization on creation at line {self.current_token.line_no}')

        # Parse the expression
        self.__next_token()
        stmt.value = self.__parse_expression(PrecedenceType.P_LOWEST)

        # Skip extra tokens until a semicolon or EOF is encountered
        max_iterations = 100  # Prevent potential infinite loops
        iterations = 0
        while not self.__current_token_is(TokenType.SEMICOLON) and not self.__current_token_is(TokenType.EOF):
            if iterations >= max_iterations:
                raise SyntaxError(f'Unexpected long statement at line {self.current_token.line_no}')
            self.__next_token()
            iterations += 1

        return stmt

    def __parse_function_statement(self) -> FunctionStatement | None:
        try:
            # Initialize FunctionStatement object
            stmt: FunctionStatement = FunctionStatement()

            # Check if IDENT is expected
            if not self.__expect_peek(TokenType.IDENT):
                return self.__handle_parse_error("Expected IDENT")

            # Set function name
            if self.current_token is None:
                return self.__handle_parse_error("Current token is None")
            stmt.name = IdentifierLiteral(value=self.current_token.literal)

            # Check if LPAREN is expected
            if not self.__expect_peek(TokenType.LPAREN):
                return self.__handle_parse_error("Expected LPAREN")

            # Parse function parameters
            stmt.parameters = self.__parse_function_parameters()

            # Check if ARROW is expected
            if not self.__expect_peek(TokenType.ARROW):
                return self.__handle_parse_error("Expected ARROW")

            # Check if TYPE is expected
            if not self.__expect_peek(TokenType.TYPE):
                return self.__handle_parse_error("Expected TYPE")

            # Set return type
            if self.current_token is None:
                return self.__handle_parse_error("Current token is None after TYPE")
            stmt.return_type = self.current_token.literal

            # Check if LBRACE is expected
            if not self.__expect_peek(TokenType.LBRACE):
                return self.__handle_parse_error("Expected LBRACE")

            # Parse function body
            stmt.body = self.__parse_block_statement()

            return stmt
        except Exception as e:
            # Capture exceptions and return None while logging the error
            return self.__handle_parse_error(f"Unexpected error: {e}")

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
            self.__handle_parse_error("Semicolon expected but not found after return expression")

        return ReturnStatement(return_value)

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

        # Ensure the statement ends with a semicolon
        if not self.__expect_peek(TokenType.SEMICOLON):
            self.__handle_parse_error("Expected ';' after assignment statement")

        # Construct and return the assignment statement
        return AssignStatement(ident=ident, operator=operator, right_value=right_value)

    def __parse_if_statement(self) -> Optional[IfStatement]:
        condition: Optional[Expression]
        consequence: Optional[BlockStatement]
        alternative: Optional[BlockStatement] = None

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

    def __parse_while_statement(self) -> Optional[WhileStatement]:
        condition: Optional[Expression]
        body: Optional[BlockStatement]

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

        # Parse condition
        if not self.__peek_token_is(TokenType.SEMICOLON):
            self.__next_token()
            condition = self.__parse_expression(PrecedenceType.P_LOWEST)
        else:
            condition = None

        # Parse action
        self.__expect_peek(TokenType.SEMICOLON)
        if not self.__peek_token_is(TokenType.RPAREN):
            self.__next_token()
            action = self.__parse_expression(PrecedenceType.P_LOWEST)
        else:
            action = None

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
    def __parse_expression(self, precedence: PrecedenceType) -> Expression | None:
        try:
            # Retrieve the prefix parsing function
            prefix_fn: Optional[Callable] = self.prefix_parse_fns.get(self.current_token.type)
            if prefix_fn is None:
                self.errors.append(f"No Prefix Parse Function for {self.current_token} found.")
                return None

            # Call the prefix parsing function with exception handling
            try:
                left_expr: Expression = prefix_fn()
            except Exception as e:
                self.errors.append(f"Error in prefix_fn execution: {e}")
                return None

            # Handle postfix expressions explicitly
            if self.__peek_token_is(TokenType.PLUS_PLUS) or self.__peek_token_is(TokenType.MINUS_MINUS):
                self.__next_token()
                left_expr = self.__parse_postfix_expression(left_expr)
                return left_expr

            # Handle infix expressions
            while not self.__peek_token_is(TokenType.SEMICOLON) and precedence.value < self.__peek_precedence().value:
                # Retrieve the infix parsing function
                infix_fn: Callable | None = self.infix_parse_fns.get(self.peek_token.type)
                if infix_fn is None:
                    # Add logging to provide more context
                    self.errors.append(f"Info: No infix parse function found for token type {self.peek_token.type}")
                    break

                # Call the infix parsing function with exception handling
                try:
                    self.__next_token()
                    left_expr = infix_fn(left_expr)
                except Exception as e:
                    self.errors.append(f"Error in infix_fn execution: {e}")
                    break

            return left_expr
        except Exception as e:
            # Catch top-level exceptions to ensure the program does not crash due to unknown err
            self.errors.append(f"Critical error in __parse_expression: {e}")
            return None

    def __parse_infix_expression(self, left_node: Expression) -> Expression:
        infix_expr: InfixExpression = InfixExpression(
            left_node = left_node,
            operator = self.current_token.literal
        )

        precedence = self.__current_precedence()

        self.__next_token()

        infix_expr.right_node = self.__parse_expression(precedence)

        return infix_expr

    def __parse_grouped_expression(self) -> Optional[Expression]:
        self.__next_token()

        expr: Expression = self.__parse_expression(PrecedenceType.P_LOWEST)

        if not self.__expect_peek(TokenType.RPAREN):
            return None

        return expr

    def __parse_call_expression(self, function: Expression) -> CallExpression:
        expr: CallExpression = CallExpression(function = function)
        expr.arguments = self.__parse_expression_list(TokenType.RPAREN)

        return expr

    def __parse_expression_list(self, end: TokenType) -> Optional[List[Expression]]:
        e_list: List[Expression] = []

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
        operator = self.current_token.literal
        return PostfixExpression(left_node = left_node, operator = operator)
    # endregion

    # region Prefix Methods
    def __parse_literal(self, literal_class: Type[Expression], converter: Callable[[str], Any]) -> Optional[Expression]:
        """
        A generic literal parsing function.

        :param literal_class: Literal class (e.g., IntegerLiteral or FloatLiteral)
        :param converter: Conversion function (e.g., int or float)
        :return: Parsed literal object, or None if parsing fails
        """

        literal_instance = literal_class()

        try:
            literal_instance.value = converter(self.current_token.literal)
        except ValueError:
            self.errors.append(f'Could not parse `{self.current_token.literal}` as a {literal_class.__name__.lower()}.')
            return None

        return literal_instance

    # TODO: add proper type enforcing for current_type
    def __parse_string_or_identifier(self, current_type: Any) -> Union[IdentifierLiteral, StringLiteral]:
        if not isinstance(self.current_token.literal, str):
            self.errors.append(f'Error at line: {self.current_token.line_no}: Invalid identifier: `{self.current_token.literal}`.')
            return current_type(value="")
        return current_type(value=self.current_token.literal)

    def __parse_int_literal(self) -> Optional[IntegerLiteral]:
        return self.__parse_literal(IntegerLiteral, int)

    def __parse_float_literal(self) -> Optional[FloatLiteral]:
        return self.__parse_literal(FloatLiteral, float)

    def __parse_boolean(self) -> BooleanLiteral:
        return BooleanLiteral(value=self.__current_token_is(bool))

    def __parse_identifier(self) -> IdentifierLiteral:
        return self.__parse_string_or_identifier(IdentifierLiteral)

    def __parse_string_literal(self) -> StringLiteral:
        return self.__parse_string_or_identifier(StringLiteral)
    # endregion
