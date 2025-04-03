import re
from typing import List, Tuple, Optional, Callable, Dict

from llvmlite import ir

from pipeline.ast import Node, NodeType, Program, ExpressionStatement, Expression, ReturnStatement, FunctionStatement, \
    BlockStatement, FunctionParameter, AssignStatement, IfStatement, WhileStatement, ForStatement, LetStatement, \
    BreakStatement, ContinueStatement, InfixExpression, CallExpression, PrefixExpression, PostfixExpression, \
    IdentifierLiteral, IntegerLiteral, FloatLiteral, BooleanLiteral, StringLiteral
from pipeline.compilation_unit.llvm_initializer import LLVMInitializer
from pipeline.environment import Environment

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
        self.errors: List[str] = []
        self.breakpoints: List[ir.Block] = []
        self.continues: List[ir.Block] = []

        self.env: Environment = Environment()
        self.llvm_initializer = LLVMInitializer()

        self.__initialize_builtins()

    def __initialize_builtins(self) -> None:
        self.env.define('printf', self.llvm_initializer.init_printf(self.module, self.type_map), ir.IntType(32))

        true_var, false_var = self.llvm_initializer.init_booleans(self.module, self.type_map)
        self.env.define('true', true_var, true_var.type)
        self.env.define('false', false_var, false_var.type)

    def __increment_counter(self) -> int:
        self.counter += 1
        return self.counter

    def add_error(self, message: str):
        self.errors.append(message)

    # Dictionaries are for nerds
    def compile(self, node: Node) -> None:
        # Convert the node type to snake_case
        type_name = node.type().name

        # Convert camelCase to snake_case (e.g., PostfixExpression -> postfix_expression)
        method_name = f"__visit_{re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', type_name).lower()}"

        # Handle name mangling for private methods (e.g., __visit_program -> _Compiler__visit_program)
        mangled_method_name = f"_{self.__class__.__name__}__{method_name[2:]}"

        # Check if the method exists using hasattr
        if hasattr(self, mangled_method_name):
            getattr(self, mangled_method_name)(node)  # Call the method dynamically
        else:
            print(f"Unhandled node type: {node.type()}")

    # region Visit Methods
    def __visit_program(self, node:
    Program) -> None:
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
            if value_type == 'bool': # TODO ugly hotfix for bool assignment
                ptr = self.builder.alloca(ir.IntType(1))  # Allocate i1 type for boolean
            else:
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
        return_value, return_type = self.__resolve_value(node.return_value)

        # Ensure the return type matches the function's return type
        if isinstance(return_type, ir.FloatType) and self.type_map['float'] != return_type:
            return_value = self.builder.sitofp(return_value, ir.FloatType())
            return_type = self.type_map['float']
        elif isinstance(return_type, ir.IntType) and self.type_map['int'] != return_type:
            return_value = self.builder.sitofp(return_value, ir.FloatType())
            return_type = self.type_map['float']

        self.builder.ret(return_value)

    def __visit_function_statement(self, node: FunctionStatement) -> None:
        name: str = node.name.value
        body: BlockStatement = node.body
        params: List[FunctionParameter] = node.parameters

        param_names: List[str] = [p.name for p in params]
        param_types: List[ir.Type] = [self.type_map[p.value_type] for p in params]

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

        # Set default return type for main
        if name == 'main' and not self.builder.block.is_terminated:
            if return_type == ir.IntType(32):
                self.builder.ret(ir.Constant(ir.IntType(32), 0))
            elif return_type == ir.FloatType():
                self.builder.ret(ir.Constant(ir.FloatType(), 0))
            elif return_type == ir.VoidType():
                self.builder.ret_void()
            else:
                raise TypeError(f"Unsupported return type for main: {return_type}")

        # Set everything back to normal after it's compiled
        self.env = previous_env
        self.env.define(name, func, return_type)

        self.builder = previous_builder

    def __visit_assign_statement(self, node: AssignStatement) -> None:
        name: str = node.ident.value
        operator: str = node.operator
        value: Expression = node.right_value

        # Check if the variable exists
        if self.env.lookup(name) is None:
            self.errors.append(f'COMPILE ERROR: Identifier {name} has not been declared before it was re-assigned')
            return

        # Resolve the right-hand value
        try:
            right_value, right_type = self.__resolve_value(value)
        except Exception as e:
            self.errors.append(f'COMPUTE ERROR: Failed to resolve value for identifier {name}: {e}')
            return

        # Get the variable pointer and original value
        var_ptr, _ = self.env.lookup(name)
        orig_value = self.builder.load(var_ptr)

        # Define supported operators
        supported_operators = {'=', '+=', '-=', '*=', '/='}

        # Check if the operator is valid
        if operator not in supported_operators:
            self.errors.append(f'COMPILE ERROR: Unsupported assignment operator "{operator}" for identifier {name}')
            return

        # Extract type information
        orig_type = orig_value.type
        right_is_int = isinstance(right_type, ir.IntType)
        right_is_float = isinstance(right_type, ir.FloatType)
        orig_is_int = isinstance(orig_type, ir.IntType)
        orig_is_float = isinstance(orig_type, ir.FloatType)

        # Helper function: Type conversion
        def convert_to_int(value):
            return self.builder.fptosi(value, ir.IntType(32)) if isinstance(value.type, ir.FloatType) else value
        def convert_to_float(value):
            return self.builder.sitofp(value, ir.FloatType()) if isinstance(value.type, ir.IntType) else value

        # Helper function: Perform operation
        def perform_operation(op, left, right):
            if op == '=':
                return right
            elif op == '+=':
                return self.builder.fadd(convert_to_float(left), convert_to_float(right))
            elif op == '-=':
                return self.builder.fsub(convert_to_float(left), convert_to_float(right))
            elif op == '*=':
                return self.builder.fmul(convert_to_float(left), convert_to_float(right))
            elif op == '/=':
                if right == 0:
                    self.errors.append(f'COMPILE ERROR: Division by zero for identifier {name}')
                    return None
                return self.builder.fdiv(convert_to_float(left), convert_to_float(right))

        # Perform the operation
        value = perform_operation(operator, orig_value, right_value)
        if value is None:
            return  # Exit if an error occurs (e.g., division by zero)

        # Ensure the types match before storing
        if isinstance(value.type, ir.FloatType) and isinstance(orig_type, ir.IntType):
            value = convert_to_int(value)
        elif isinstance(value.type, ir.IntType) and isinstance(orig_type, ir.FloatType):
            value = convert_to_float(value)

        # Store the result
        self.builder.store(value, var_ptr)

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

    def __visit_for_statement(self, node: ForStatement) -> None:
        var_declaration: LetStatement = node.var_declaration
        condition: Expression = node.condition
        action: AssignStatement = node.action
        body: BlockStatement = node.body

        previous_env = self.env
        self.env = Environment(parent = previous_env)

        self.compile(var_declaration)

        for_loop_entry = self.builder.append_basic_block(f'for_loop_entry_{self.__increment_counter()}')
        for_loop_otherwise = self.builder.append_basic_block(f'for_loop_otherwise_{self.counter}')

        self.breakpoints.append(for_loop_otherwise)
        self.continues.append(for_loop_entry)

        self.builder.branch(for_loop_entry)
        self.builder.position_at_start(for_loop_entry)

        self.compile(body)
        self.compile(action)

        test, _ = self.__resolve_value(condition)

        self.builder.cbranch(test, for_loop_entry, for_loop_otherwise)

        self.builder.position_at_start(for_loop_otherwise)

        self.breakpoints.pop()
        self.continues.pop()

    def __visit_break_statement(self, node: BreakStatement) -> None:
        self.builder.branch(self.breakpoints[-1])

    def __visit_continue_statement(self, node: ContinueStatement) -> None:
        self.builder.branch(self.continues[-1])
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
        elif isinstance(left_type, ir.FloatType) and isinstance(left_value,
                                                                ir.IntType) and left_type.width == 1:  # i1 (bool)
            left_value = self.builder.zext(left_value, ir.IntType(32))  # Zero-extend to i32, then convert to float
            left_value = self.builder.sitofp(left_value, ir.FloatType())
            left_type = ir.FloatType()

        if isinstance(right_type, ir.IntType) and right_type.width == 1:  # i1 (bool)
            right_value = self.builder.zext(right_value, ir.IntType(32))  # Zero-extend to i32
            right_type = ir.IntType(32)
        elif isinstance(right_type, ir.FloatType) and isinstance(right_value,
                                                                 ir.IntType) and right_type.width == 1:  # i1 (bool)
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
            result_type = self.type_map['float']
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
        params: List[Expression] = node.arguments

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

    def __visit_prefix_expression(self, node: PrefixExpression) -> tuple[ir.Value, ir.Type]:
        operator: str = node.operator
        right_node: Expression = node.right_node

        right_value, right_type = self.__resolve_value(right_node)

        Type, value = None, None
        if isinstance(right_type, ir.FloatType):
            Type = ir.FloatType()
            match operator:
                case '-': value = self.builder.fmul(right_value, ir.Constant(ir.FloatType(), -1.0))
                case '!': value = ir.Constant(ir.IntType(1), 0)
        elif isinstance(right_type, ir.IntType):
            match operator:
                case '-': value = self.builder.mul(right_value, ir.Constant(ir.IntType(32), -1))
                case '!': value = self.builder.not_(right_value)

        return value, Type

    def __visit_postfix_expression(self, node: PostfixExpression) -> None:
        left_node: IdentifierLiteral = node.left_node # this is an expression but should be an identifier literal
        operator: str = node.operator

        if self.env.lookup(left_node.value) is None:
            self.add_error(f'Identifier {left_node.value} has not been declared before it was used in a PostfixExpression')

        var_ptr, _ = self.env.lookup(left_node.value)
        orig_value = self.builder.load(var_ptr)

        value = None
        match operator:
            case '++':
                if isinstance(orig_value.type, ir.IntType):
                    value = self.builder.add(orig_value, ir.Constant(ir.IntType(32), 1))
                elif isinstance(orig_value.type, ir.FloatType):
                    value = self.builder.fadd(orig_value, ir.Constant(ir.FloatType(), 1.0))
            case '--':
                if isinstance(orig_value.type, ir.IntType):
                    value = self.builder.sub(orig_value, ir.Constant(ir.IntType(32), 1))
                elif isinstance(orig_value.type, ir.FloatType):
                    value = self.builder.fsub(orig_value, ir.Constant(ir.FloatType(), 1.0))

        self.builder.store(value, var_ptr)
    # endregion

    # endregion

    # region Helper Methods
    def __resolve_value(self, node: Expression) -> Optional[Tuple[ir.Value, ir.Type]]:
        match node.type():
            case NodeType.IntegerLiteral:
                node: IntegerLiteral = node
                value, Type = node.value, self.type_map['int']
                return ir.Constant(Type, value), Type
            case NodeType.FloatLiteral:
                node: FloatLiteral = node
                value, Type = node.value, self.type_map['float']
                return ir.Constant(Type, value), Type
            case NodeType.IdentifierLiteral:
                node: IdentifierLiteral = node
                ptr, Type = self.env.lookup(node.value)
                return self.builder.load(ptr), Type
            case NodeType.BooleanLiteral:
                node: BooleanLiteral = node
                return ir.Constant(ir.IntType(1), 1 if node.value else 0), ir.IntType(1)
            case NodeType.StringLiteral:
                node: StringLiteral = node
                string, Type = self.__convert_string(node.value)
                return string, Type

            # Expressions
            case NodeType.InfixExpression:
                return self.__visit_infix_expression(node)
            case NodeType.CallExpression:
                return self.__visit_call_expression(node)
            case NodeType.PostfixExpression:
                return self.__visit_postfix_expression(node)

    def __convert_string(self, string: str) -> tuple[ir.Constant, ir.ArrayType]:
        string = string.replace('\\n', '\n\0')

        fmt: str = f'{string}\0'
        c_fmt: ir.Constant = ir.Constant(ir.ArrayType(ir.IntType(8), len(fmt)), bytearray(fmt.encode('utf8')))

        global_fmt = ir.GlobalVariable(self.module, c_fmt.type, name = f'__str_{self.__increment_counter()}')
        global_fmt.linkage = 'internal'
        global_fmt.global_constant = True
        global_fmt.initializer = c_fmt

        return global_fmt, global_fmt.type

    def builtin_printf(self, params: List[ir.Instruction], return_type: ir.Type) -> None:
        func, _ = self.env.lookup('printf')

        c_str = self.builder.alloca(return_type)
        self.builder.store(params[0], c_str)

        rest_params = params[1:]

        if isinstance(params[0], ir.LoadInstr):
            c_fmt: ir.LoadInstr = params[0]
            g_var_ptr = c_fmt.operands[0]
            string_val = self.builder.load(g_var_ptr)
            fmt_arg = self.builder.bitcast(string_val, ir.IntType(8).as_pointer())
        else:
            # Convert the format string to a global variable
            fmt_arg = self.builder.bitcast(self.module.get_global(f'__str_{self.counter}'), ir.IntType(8).as_pointer())

        # Prepare the arguments for printf
        args = [fmt_arg]
        for param in rest_params:
            if isinstance(param.type, ir.FloatType):
                # Bitcast float to double for printf compatibility
                param = self.builder.fpext(param, ir.DoubleType())
            args.append(param)

        return self.builder.call(func, args)
    # endregion