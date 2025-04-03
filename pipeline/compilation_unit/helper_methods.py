from typing import Tuple, Optional, List
from llvmlite import ir

from pipeline.ast import Expression, IntegerLiteral, FloatLiteral, IdentifierLiteral, BooleanLiteral, StringLiteral

class HelperMethods:
    def __init__(self, compiler):
        self.compiler = compiler

    def resolve_value(self, node: Expression) -> Optional[Tuple[ir.Value, ir.Type]]:
        match node.type():
            case 'IntegerLiteral':
                node: IntegerLiteral = node
                value, Type = node.value, self.compiler.type_map['int']
                return ir.Constant(Type, value), Type
            case 'FloatLiteral':
                node: FloatLiteral = node
                value, Type = node.value, self.compiler.type_map['float']
                return ir.Constant(Type, value), Type
            case 'IdentifierLiteral':
                node: IdentifierLiteral = node
                ptr, Type = self.compiler.env.lookup(node.value)
                return self.compiler.builder.load(ptr), Type
            case 'BooleanLiteral':
                node: BooleanLiteral = node
                return ir.Constant(ir.IntType(1), 1 if node.value else 0), ir.IntType(1)
            case 'StringLiteral':
                node: StringLiteral = node
                string, Type = self.convert_string(node.value)
                return string, Type

            # Expressions
            case 'InfixExpression':
                return self.compiler.expression_visitor.visit_infix_expression(node)
            case 'CallExpression':
                return self.compiler.expression_visitor.visit_call_expression(node)
            case 'PostfixExpression':
                return self.compiler.expression_visitor.visit_postfix_expression(node)

    def convert_string(self, string: str) -> tuple[ir.Constant, ir.ArrayType]:
        string = string.replace('\\n', '\n\0')

        fmt: str = f'{string}\0'
        c_fmt: ir.Constant = ir.Constant(ir.ArrayType(ir.IntType(8), len(fmt)), bytearray(fmt.encode('utf8')))

        global_fmt = ir.GlobalVariable(self.compiler.module, c_fmt.type, name=f'__str_{self.compiler.__increment_counter()}')
        global_fmt.linkage = 'internal'
        global_fmt.global_constant = True
        global_fmt.initializer = c_fmt

        return global_fmt, global_fmt.type
