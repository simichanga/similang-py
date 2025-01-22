from llvmlite import ir

from __imports__ import *

from Environment import Environment

class Compiler:
    def __init__(self) -> None:
        self.type_map: dict[str, ir.Type] = {
            'int': ir.IntType(32),
            'float': ir.FloatType(),
            'bool': ir.IntType(1),

            'str': ir.PointerType(ir.IntType(8)),
            'void': ir.VoidType(),
        }

        self.module: ir.Module = ir.Module('main')

        self.builder: ir.IRBuilder = ir.IRBuilder()

        self.counter: int = 0

        self.env: Environment = Environment()

        self.errors: list[str] = []

        self.__initialize_builtins()

    def __initialize_builtins(self) -> None:
        def __init_print() -> ir.Function:
            fnty: ir.FunctionType = ir.FunctionType(
                self.type_map['int'],
                [ir.IntType(8).as_pointer()],
                var_arg = True
            )
            return ir.Function(self.module, fnty, 'printf')

        def __init__booleans() -> tuple[ir.GlobalVariable, ir.GlobalVariable]:
            bool_type: ir.Type = self.type_map['bool']

            true_var = ir.GlobalVariable(self.module, bool_type, 'true')
            true_var.initializer = ir.Constant(bool_type, 1)
            true_var.global_constant = True

            false_var = ir.GlobalVariable(self.module, bool_type, 'false')
            false_var.initializer = ir.Constant(bool_type, 0)
            false_var.global_constant = True

            return true_var, false_var

        self.env.define('printf', __init_print(), ir.IntType(32))

        true_var, false_var = __init__booleans()
        self.env.define('true', true_var, true_var.type)
        self.env.define('false', false_var, false_var.type)

    def __increment_counter(self) -> int:
        self.counter += 1
        return self.counter

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
            case NodeType.AssignStatement:
                self.__visit_assign_statement(node)
            case NodeType.IfStatement:
                self.__visit_if_statement(node)
            case NodeType.WhileStatement:
                self.__visit_while_statement(node)

            case NodeType.InfixExpression:
                self.__visit_infix_expression(node)
            case NodeType.CallExpression:
                self.__visit_call_expression(node)

    
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
        params: list[FunctionParameter] = node.parameters

        param_names: list[str] = [p.name for p in params]
        param_types: list[ir.Type] = [self.type_map[p.value_type] for p in params]

        return_type: ir.Type = self.type_map[node.return_type]

        fnty: ir.FunctionType = ir.FunctionType(return_type, param_types)
        func: ir.Function = ir.Function(self.module, fnty, name = name)

        block: ir.Block = func.append_basic_block(f'{name}_entry')

        previous_builder = self.builder
        self.builder = ir.IRBuilder(block)

        # Storing pointers for each parameter
        params_ptr = []
        for i, typ in enumerate(param_types):
            ptr = self.builder.alloca(typ)
            self.builder.store(func.args[i], ptr)
            params_ptr.append(ptr)

        # Adding the parameters to the env
        previous_env = self.env
        self.env = Environment(parent = self.env)
        for i, x in enumerate(zip(param_types, param_names)):
            typ = param_types[i]
            ptr = params_ptr[i]

            self.env.define(x[1], ptr, typ)

        self.env.define(name, func, return_type)

        self.compile(body)

        # Set everything back to normal after it's compiled
        self.env = previous_env
        self.env.define(name, func, return_type)

        self.builder = previous_builder
    
    def __visit_assign_statement(self, node: AssignStatement) -> None:
        name: str = node.ident.value
        value: Expression = node.right_value

        value, Type = self.__resolve_value(value)

        if self.env.lookup(name) is None:
            self.errors.append(f'COMPILE ERROR: Identifier {name} has not been declared before it was re-assigned') # TODO proper error throwing
        else:
            ptr, _ = self.env.lookup(name)
            self.builder.store(value, ptr)

    def __visit_if_statement(self, node: IfStatement) -> None:
        condition = node.condition
        consequence = node.consequence
        alternative = node.alternative

        test, _ = self.__resolve_value(condition)

        if alternative is None:
            with self.builder.if_then(test):
                self.compile(consequence)
        else:
            with self.builder.if_else(test) as (true, otherwise):
                with true:
                    self.compile(consequence)
                with otherwise:
                    self.compile(alternative)
    def __visit_while_statement(self, node: WhileStatement) -> None:
        condition: Expression = node.condition
        body: BlockStatement = node.body

        test, _ = self.__resolve_value(condition)

        while_loop_entry = self.builder.append_basic_block(f'while_loop_entry_{self.__increment_counter()}')
        while_loop_otherwise = self.builder.append_basic_block(f'while_loop_otherwise_{self.counter}')

        self.builder.cbranch(test, while_loop_entry, while_loop_otherwise)
        self.builder.position_at_start(while_loop_entry)
        self.compile(body)
        test, _ = self.__resolve_value(condition)

        self.builder.cbranch(test, while_loop_entry, while_loop_otherwise)
        self.builder.position_at_start(while_loop_otherwise)
    # endregion

    # region Expressions
    def __visit_infix_expression(self, node: InfixExpression) -> tuple[ir.Value, ir.Type]:
        operator: str = node.operator
        left_value, left_type = self.__resolve_value(node.left_node)
        right_value, right_type = self.__resolve_value(node.right_node)

        # Implicit type conversion for booleans
        if isinstance(left_type, ir.IntType) and left_type.width == 1:  # i1 (bool)
            left_value = self.builder.zext(left_value, ir.IntType(32))  # Zero-extend to i32
            left_type = ir.IntType(32)
        elif isinstance(left_type, ir.FloatType) and isinstance(left_value, ir.IntType) and left_type.width == 1:  # i1 (bool)
            left_value = self.builder.zext(left_value, ir.IntType(32))  # Zero-extend to i32, then convert to float
            left_value = self.builder.sitofp(left_value, ir.FloatType())
            left_type = ir.FloatType()

        if isinstance(right_type, ir.IntType) and right_type.width == 1:  # i1 (bool)
            right_value = self.builder.zext(right_value, ir.IntType(32))  # Zero-extend to i32
            right_type = ir.IntType(32)
        elif isinstance(right_type, ir.FloatType) and isinstance(right_value, ir.IntType) and right_type.width == 1:  # i1 (bool)
            right_value = self.builder.zext(right_value, ir.IntType(32))  # Zero-extend to i32, then convert to float
            right_value = self.builder.sitofp(right_value, ir.FloatType())
            right_type = ir.FloatType()

        # Implicit conversion between int and float
        if isinstance(left_type, ir.IntType) and isinstance(right_type, ir.FloatType):
            left_value = self.builder.sitofp(left_value, ir.FloatType())
            left_type = ir.FloatType()
        elif isinstance(left_type, ir.FloatType) and isinstance(right_type, ir.IntType):
            right_value = self.builder.sitofp(right_value, ir.FloatType())
            right_type = ir.FloatType()

        value, result_type = None, None

        # Handle integer operations
        if isinstance(left_type, ir.IntType) and isinstance(right_type, ir.IntType):
            result_type = self.type_map['int']
            value = self.__process_int_operations(operator, left_value, right_value)

        # Handle floating-point operations
        elif isinstance(left_type, ir.FloatType) and isinstance(right_type, ir.FloatType):
            result_type = ir.FloatType()
            value = self.__process_float_operations(operator, left_value, right_value)

        # Error if types are incompatible
        if value is None:
            raise TypeError(f"Unsupported operand types for operator '{operator}': {left_type}, {right_type}")

        return value, result_type

    def __process_int_operations(self, operator: str, left_value, right_value) -> ir.Value:
        match operator:
            case '+': return self.builder.add(left_value, right_value)
            case '-': return self.builder.sub(left_value, right_value)
            case '*': return self.builder.mul(left_value, right_value)
            case '/': return self.builder.sdiv(left_value, right_value)
            case '%': return self.builder.srem(left_value, right_value)
            case '<': return self.builder.icmp_signed('<', left_value, right_value)
            case '<=': return self.builder.icmp_signed('<=', left_value, right_value)
            case '>': return self.builder.icmp_signed('>', left_value, right_value)
            case '>=': return self.builder.icmp_signed('>=', left_value, right_value)
            case '==': return self.builder.icmp_signed('==', left_value, right_value)
            case '!=': return self.builder.icmp_signed('!=', left_value, right_value)
            case _: raise ValueError(f"Unsupported operator for integers: {operator}")

    def __process_float_operations(self, operator: str, left_value, right_value) -> ir.Value:
        match operator:
            case '+': return self.builder.fadd(left_value, right_value)
            case '-': return self.builder.fsub(left_value, right_value)
            case '*': return self.builder.fmul(left_value, right_value)
            case '/': return self.builder.fdiv(left_value, right_value)
            case '%': return self.builder.frem(left_value, right_value)
            case '<': return self.builder.fcmp_ordered('<', left_value, right_value)
            case '<=': return self.builder.fcmp_ordered('<=', left_value, right_value)
            case '>': return self.builder.fcmp_ordered('>', left_value, right_value)
            case '>=': return self.builder.fcmp_ordered('>=', left_value, right_value)
            case '==': return self.builder.fcmp_ordered('==', left_value, right_value)
            case '!=': return self.builder.fcmp_ordered('!=', left_value, right_value)
            case _: raise ValueError(f"Unsupported operator for floats: {operator}")


    def __visit_call_expression(self, node: CallExpression) -> tuple[ir.Value, ir.Type]:
        name: str = node.function.value
        params: list[Expression] = node.arguments

        # Resolve parameters
        args, types = [], []
        for param in params:
            arg_value, arg_type = self.__resolve_value(param)
            args.append(arg_value)
            types.append(arg_type)

        # Handle built-in functions like 'printf'
        if name == 'printf':
            if not types:
                raise ValueError("'printf' requires at least one argument")
            ret = self.builtin_printf(params=args, return_type=types[0])
            ret_type = self.type_map['int']
        else:
            # Lookup custom functions in the environment
            func, ret_type = self.env.lookup(name)
            ret = self.builder.call(func, args)

        return ret, ret_type
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
                node: IdentifierLiteral = node
                ptr, Type = self.env.lookup(node.value)
                return self.builder.load(ptr), Type
            case NodeType.BooleanLiteral:
                node: BooleanLiteral = node
                return ir.Constant(ir.IntType(1), 1 if node.value else 0), ir.IntType
            case NodeType.StringLiteral:
                node: StringLiteral = node
                string, Type = self.__convert_string(node.value)
                return string, Type

            # Expression Values
            case NodeType.InfixExpression:
                return self.__visit_infix_expression(node)
            case NodeType.CallExpression:
                return self.__visit_call_expression(node)

    def __convert_string(self, string: str) -> tuple[ir.Constant, ir.ArrayType]:
        string = string.replace('\\n', '\n\0')

        fmt: str = f'{string}\0'
        c_fmt: ir.Constant = ir.Constant(ir.ArrayType(ir.IntType(8), len(fmt)), bytearray(fmt.encode('utf8')))

        global_fmt = ir.GlobalVariable(self.module, c_fmt.type, name = f'__str_{self.__increment_counter()}')
        global_fmt.linkage = 'internal'
        global_fmt.global_constant = True
        global_fmt.initializer = c_fmt

        return global_fmt, global_fmt.type
    
    def builtin_printf(self, params: list[ir.Instruction], return_type: ir.Type) -> None:
        func, _ = self.env.lookup('printf')

        c_str = self.builder.alloca(return_type)
        self.builder.store(params[0], c_str)

        rest_params = params[1:]

        if isinstance(params[0], ir.LoadInstr):
            c_fmt: ir.LoadInstr = params[0]
            g_var_ptr = c_fmt.operands[0]
            string_val = self.builder.load(g_var_ptr)
            fmt_arg = self.builder.bitcast(string_val, ir.IntType(8).as_pointer())
            return self.builder.call(func, [fmt_arg, *rest_params])
        else:
            # TODO handle printing floats
            fmt_arg = self.builder.bitcast(self.module.get_global(f'__str_{self.counter}'), ir.IntType(8).as_pointer())

            return self.builder.call(func, [fmt_arg, *rest_params])
    # endregion