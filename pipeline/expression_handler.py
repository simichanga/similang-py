from typing import List

from llvmlite import ir
from pipeline.ast import Expression, InfixExpression, CallExpression, PrefixExpression, PostfixExpression, \
    IdentifierLiteral


class ExpressionHandler:
    def __init__(self, compiler):
        self.compiler = compiler
        self.builder = compiler.builder
        
    def compile(self, node: Expression) -> tuple[ir.Value, ir.Type]:
        node_type = node.type()
        match node_type:
            case node_type.IntegerLiteral:
                return self.handle_integer_literal(node)
            case node_type.FloatLiteral:
                return self.handle_float_literal(node)
            case node_type.IdentifierLiteral:
                return self.handle_identifier(node)
            case node_type.BooleanLiteral:
                return self.handle_boolean_literal(node)
            case node_type.StringLiteral:
                return self.handle_string_literal(node)
            case node_type.InfixExpression:
                return self.handle_infix_expression(node)
            case node_type.CallExpression:
                return self.handle_call_expression(node)
            case node_type.PostfixExpression:
                return self.handle_postfix_expression(node)
            case _:
                raise ValueError(f"Unsupported expression type: {node_type}")
                
    def handle_integer_literal(self, node):
        return ir.Constant(self.compiler.type_system.get_type('int'), node.value), self.compiler.type_system.get_type('int')
        
    def handle_float_literal(self, node):
        return ir.Constant(self.compiler.type_system.get_type('float'), node.value), self.compiler.type_system.get_type('float')
        
    def handle_identifier(self, node):
        ptr, Type = self.compiler.env.lookup(node.value)
        return self.compiler.builder.load(ptr), Type
        
    def handle_boolean_literal(self, node):
        value = 1 if node.value else 0
        const = ir.Constant(ir.IntType(1), value)
        return const, ir.IntType(1)
        
    def handle_string_literal(self, node):
        # Implementation for string literals
        pass
        
    def handle_infix_expression(self, node):
        # Implementation for infix expressions
        operator: str = node.operator
        left_value, left_type = self.compile(node.left_node)
        right_value, right_type = self.compile(node.right_node)

        # Implicit type conversion for booleans
        if isinstance(left_type, ir.IntType) and left_type.width == 1:  # i1 (bool)
            left_value = self.compiler.builder.zext(left_value, ir.IntType(32))  # Zero-extend to i32
            left_type = ir.IntType(32)
        elif isinstance(left_type, ir.FloatType) and isinstance(left_value, ir.IntType) and left_type.width == 1:  # i1 (bool)
            left_value = self.compiler.builder.zext(left_value, ir.IntType(32))  # Zero-extend to i32, then convert to float
            left_value = self.compiler.builder.sitofp(left_value, ir.FloatType())
            left_type = ir.FloatType()

        if isinstance(right_type, ir.IntType) and right_type.width == 1:  # i1 (bool)
            right_value = self.compiler.builder.zext(right_value, ir.IntType(32))  # Zero-extend to i32
            right_type = ir.IntType(32)
        elif isinstance(right_type, ir.FloatType) and isinstance(right_value, ir.IntType) and right_type.width == 1:  # i1 (bool)
            right_value = self.compiler.builder.zext(right_value, ir.IntType(32))  # Zero-extend to i32, then convert to float
            right_value = self.compiler.builder.sitofp(right_value, ir.FloatType())
            right_type = ir.FloatType()

        # Implicit conversion between int and float
        if isinstance(left_type, ir.IntType) and isinstance(right_type, ir.FloatType):
            left_value = self.compiler.builder.sitofp(left_value, ir.FloatType())
            left_type = ir.FloatType()
        elif isinstance(left_type, ir.FloatType) and isinstance(right_type, ir.IntType):
            right_value = self.compiler.builder.sitofp(right_value, ir.FloatType())
            right_type = ir.FloatType()

        value, result_type = None, None

        # Handle integer operations
        if isinstance(left_type, ir.IntType) and isinstance(right_type, ir.IntType):
            result_type = self.compiler.type_system.get_type('int')
            value = self.compiler._process_int_operations(operator, left_value, right_value)

        # Handle floating-point operations
        elif isinstance(left_type, ir.FloatType) and isinstance(right_type, ir.FloatType):
            result_type = self.compiler.type_system.get_type('float')
            value = self.compiler._process_float_operations(operator, left_value, right_value)

        # Handle comparison operations that return boolean (i1)
        elif operator in ['==', '!=', '<', '<=', '>', '>=']:
            if isinstance(left_type, ir.IntType) and isinstance(right_type, ir.IntType):
                value = self.compiler.builder.icmp_signed(operator, left_value, right_value)
            elif isinstance(left_type, ir.FloatType) and isinstance(right_type, ir.FloatType):
                value = self.compiler.builder.fcmp_ordered(operator, left_value, right_value)
            result_type = ir.IntType(1)  # i1 type for boolean

        # Error if types are incompatible
        if value is None:
            raise TypeError(f"Unsupported operand types for operator '{operator}': {left_type}, {right_type}")

        return value, result_type
        
    def handle_call_expression(self, node):
        # Implementation for function calls
        name: str = node.function.value
        params: List[Expression] = node.arguments

        # Resolve parameters
        args, types = [], []
        for param in params:
            arg_value, arg_type = self.compile(param)
            args.append(arg_value)
            types.append(arg_type)

        # Handle built-in functions like 'printf'
        if name == 'printf':
            if not types:
                raise ValueError("'printf' requires at least one argument")
            ret = self.compiler.builtin_printf(params=args, return_type=types[0])
            ret_type = self.compiler.type_system.get_type('int')
        else:
            # Lookup custom functions in the environment
            func, ret_type = self.compiler.env.lookup(name)
            ret = self.compiler.builder.call(func, args)

        return ret, ret_type
        
    def handle_postfix_expression(self, node):
        # Implementation for postfix expressions
        left_node: IdentifierLiteral = node.left_node # this is an expression but should be an identifier literal
        operator: str = node.operator

        if self.compiler.env.lookup(left_node.value) is None:
            self.compiler.add_error(f'Identifier {left_node.value} has not been declared before it was used in a PostfixExpression')

        var_ptr, _ = self.compiler.env.lookup(left_node.value)
        orig_value = self.compiler.builder.load(var_ptr)

        value = None
        match operator:
            case '++':
                if isinstance(orig_value.type, ir.IntType):
                    value = self.compiler.builder.add(orig_value, ir.Constant(ir.IntType(32), 1))
                elif isinstance(orig_value.type, ir.FloatType):
                    value = self.compiler.builder.fadd(orig_value, ir.Constant(ir.FloatType(), 1.0))
            case '--':
                if isinstance(orig_value.type, ir.IntType):
                    value = self.compiler.builder.sub(orig_value, ir.Constant(ir.IntType(32), 1))
                elif isinstance(orig_value.type, ir.FloatType):
                    value = self.compiler.builder.fsub(orig_value, ir.Constant(ir.FloatType(), 1.0))

        self.compiler.builder.store(value, var_ptr)
        return value, orig_value.type # Return the value and its type
