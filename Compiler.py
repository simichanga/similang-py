from llvmlite import ir

from __imports__ import *

from Environment import Environment

class Compiler:
    def __init__(self) -> None:
        self.type_map: dict[str, ir.Type] = {
            'int': ir.IntType(32),
            'float': ir.FloatType(),
        }

        self.module: ir.Module = ir.Module('main')

        self.builder: ir.IRBuilder = ir.IRBuilder()

        self.env: Environment = Environment()

    def compile(self, node: Node) -> None:
        match node.type():
            case NodeType.Program:
                self.__visit_program(node)

            case NodeType.ExpressionStatement:
                self.__visit_expression_statement(node)
            case NodeType.LetStatement:
                self.__visit_let_statement(node)
            case NodeType.FunctionStatement:
                self.__visit_function_statement(node)
            case NodeType.BlockStatement:
                self.__visit_block_statement(node)
            case NodeType.ReturnStatement:
                self.__visit_return_statement(node)


            case NodeType.InfixExpression:
                self.__visit_infix_expression(node)

    
    # region Visit Methods
    def __visit_program(self, node: Program) -> None:
        for stmt in node.statements:
            self.compile(stmt)

    # region Statements
    def __visit_expression_statement(self, node: ExpressionStatement) -> None:
        self.compile(node.expr)

    def __visit_let_statement(self, node: ExpressionStatement) -> None:
        name: str = node.name.value
        value: Expression = node.value
        value_type = node.value_type # TODO implement when actually doing type checking

        value, Type = self.__resolve_value(node = value)

        if self.env.lookup(name) is None:
            # Define and allocate the variable
            ptr = self.builder.alloca(Type)

            # Store the value at the ptr
            self.builder.store(value, ptr)

            # Add the value to the env
            self.env.define(name, ptr, Type)
        else:
            ptr, _ = self.env.lookup(name)
            self.builder.store(value, ptr)

    def __visit_block_statement(self, node: BlockingIOError) -> None:
        for stmt in node.statements:
            self.compile(stmt)

    def __visit_return_statement(self, node: ReturnStatement) -> None:
        value: Expression = node.return_value
        value, Type = self.__resolve_value(value)

        self.builder.ret(value)

    def __visit_function_statement(self, node: FunctionStatement) -> None:
        name: str = node.name.value
        body: BlockStatement = node.body
        params: list[IdentifierLiteral] = node.parameters

        param_names: list[str] = [p.value for p in params]
        param_types: list[ir.Type] = [] # TODO

        return_type: ir.Type = self.type_map[node.return_type]

        fnty: ir.FunctionType = ir.FunctionType(return_type, param_types)
        func: ir.Function = ir.Function(self.module, fnty, name = name)

        block: ir.Block = func.append_basic_block(f'{name}_entry')

        previous_builder = self.builder
        self.builder = ir.IRBuilder(block)

        previous_env = self.env
        self.env = Environment(parent = self.env)
        self.env.define(name, func, return_type)

        self.compile(body)

        self.env = previous_env
        self.env.define(name, func, return_type)

        self.builder = previous_builder

    # endregion

    # region Expressions
    def __visit_infix_expression(self, node: InfixExpression) -> None:
        operator: str = node.operator
        left_value, left_type = self.__resolve_value(node.left_node)
        right_value, right_type = self.__resolve_value(node.right_node)

        value, Type = None, None

        if isinstance(right_type, ir.IntType) and isinstance(left_type, ir.IntType):
            Type = self.type_map['int']
            OP_MAP: Final[dict[str, Callable]] = {
                '+': self.builder.add,
                '-': self.builder.sub,
                '*': self.builder.mul,
                '/': self.builder.sdiv,
                '%': self.builder.srem,
            }
            value = OP_MAP[operator](left_value, right_value)

        elif isinstance(right_type, ir.FloatType) and isinstance(left_type, ir.FloatType):
            Type = ir.FloatType()
            OP_MAP: Final[dict[str, Callable]] = {
                '+': self.builder.fadd,
                '-': self.builder.fsub,
                '*': self.builder.fmul,
                '/': self.builder.fdiv,
                '%': self.builder.frem,
            }
            value = OP_MAP[operator](left_value, right_value)
        
        return value, Type
    # endregion

    # endregion

    # region Helper Methods
    def __resolve_value(self, node: Expression) -> tuple[ir.Value, ir.Type]: # TODO implement value_type parameter
        match node.type():
            case NodeType.IntegerLiteral:
                node: IntegerLiteral = node
                value, Type = node.value, self.type_map['int'] # value type checking here
                return ir.Constant(Type, value), Type
            case NodeType.FloatLiteral:
                node: FloatLiteral = node
                value, Type = node.value, self.type_map['float'] # value type checking here
                return ir.Constant(Type, value), Type
            case NodeType.IdentifierLiteral:
                node: FloatLiteral = node
                ptr, Type = self.env.lookup(node.value)
                return self.builder.load(ptr), Type

            # Expression Values
            case NodeType.InfixExpression:
                return self.__visit_infix_expression(node)

    # endregion