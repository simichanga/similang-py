from typing import Tuple, Optional, List
from llvmlite import ir
from pipeline.ast import (
    InfixExpression, PrefixExpression, PostfixExpression, CallExpression,
    IntegerLiteral, FloatLiteral, IdentifierLiteral, BooleanLiteral, StringLiteral, Expression
)

class ExpressionVisitor:
    def __init__(self, compiler):
        self.compiler = compiler

    def visit_infix_expression(self, node: InfixExpression) -> Tuple[ir.Value, ir.Type]:
        try:
            operator: str = node.operator
            left_value, left_type = self.compiler.__resolve_value(node.left_node)
            right_value, right_type = self.compiler.__resolve_value(node.right_node)

            # Ensure left and right values are not None
            if left_value is None or left_type is None or right_value is None or right_type is None:
                raise ValueError("Resolved value or type cannot be None")

            # Helper function to handle implicit type conversions
            def convert_to_common_type(value, type_):
                if isinstance(type_, ir.IntType) and type_.width == 1:  # i1 (bool)
                    return self.compiler.builder.zext(value, ir.IntType(32)), ir.IntType(32)
                elif isinstance(type_, ir.FloatType) and isinstance(value, ir.IntType) and type_.width == 1:  # i1 (bool)
                    int_value = self.compiler.builder.zext(value, ir.IntType(32))
                    return self.compiler.builder.sitofp(int_value, ir.FloatType()), ir.FloatType()
                return value, type_

            # Apply implicit type conversion for booleans
            left_value, left_type = convert_to_common_type(left_value, left_type)
            right_value, right_type = convert_to_common_type(right_value, right_type)

            # Implicit conversion between int and float
            if isinstance(left_type, ir.IntType) and isinstance(right_type, ir.FloatType):
                left_value = self.compiler.builder.sitofp(left_value, ir.FloatType())
                left_type = ir.FloatType()
            elif isinstance(left_type, ir.FloatType) and isinstance(right_type, ir.IntType):
                right_value = self.compiler.builder.sitofp(right_value, ir.FloatType())
                right_type = ir.FloatType()

            # Handle integer operations
            if isinstance(left_type, ir.IntType) and isinstance(right_type, ir.IntType):
                result_type = self.compiler.type_map['int']
                value = self.compiler.__process_int_operations(operator, left_value, right_value)

            # Handle floating-point operations
            elif isinstance(left_type, ir.FloatType) and isinstance(right_type, ir.FloatType):
                result_type = self.compiler.type_map['float']
                value = self.compiler.__process_float_operations(operator, left_value, right_value)

            # Error if types are incompatible
            if value is None:
                raise TypeError(f"Unsupported operand types for operator '{operator}': {left_type}, {right_type}")

            return value, result_type

        except Exception as e:
            raise RuntimeError(f"Error processing infix expression: {e}")

    def visit_prefix_expression(self, node: PrefixExpression) -> Tuple[ir.Value, ir.Type]:
        operator: str = node.operator
        right_node: Expression = node.right_node

        right_value, right_type = self.compiler.__resolve_value(right_node)

        Type, value = None, None
        if isinstance(right_type, ir.FloatType):
            Type = ir.FloatType()
            match operator:
                case '-': value = self.compiler.builder.fmul(right_value, ir.Constant(ir.FloatType(), -1.0))
                case '!': value = ir.Constant(ir.IntType(1), 0)
        elif isinstance(right_type, ir.IntType):
            match operator:
                case '-': value = self.compiler.builder.mul(right_value, ir.Constant(ir.IntType(32), -1))
                case '!': value = self.compiler.builder.not_(right_value)

        return value, Type

    def visit_postfix_expression(self, node: PostfixExpression) -> None:
        left_node: IdentifierLiteral = node.left_node  # this is an expression but should be an identifier literal
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

    def visit_call_expression(self, node: CallExpression) -> Tuple[ir.Value, ir.Type]:
        name: str = node.function.value
        params: List[Expression] = node.arguments

        # Resolve parameters
        args, types = [], []
        for param in params:
            arg_value, arg_type = self.compiler.__resolve_value(param)
            args.append(arg_value)
            types.append(arg_type)

        # Handle built-in functions like 'printf'
        if name == 'printf':
            if not types:
                raise ValueError("'printf' requires at least one argument")
            ret = self.compiler.builtin_printf(params=args, return_type=types[0])
            ret_type = self.compiler.type_map['int']
        else:
            # Lookup custom functions in the environment
            func, ret_type = self.compiler.env.lookup(name)
            ret = self.compiler.builder.call(func, args)

        return ret, ret_type
