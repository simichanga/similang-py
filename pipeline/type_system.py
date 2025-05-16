from llvmlite import ir
from typing import Tuple, Optional

class TypeSystem:
    def __init__(self):
        self.type_map = {
            'int': ir.IntType(32),
            'float': ir.FloatType(),
            'bool': ir.IntType(1),
            'str': ir.PointerType(ir.IntType(8)),
            'void': ir.VoidType(),
        }

    def get_type(self, type_name: str) -> Optional[ir.Type]:
        return self.type_map.get(type_name)

    def coerce_types(self, builder, left: ir.Value, right: ir.Value) -> Tuple[ir.Value, ir.Value]:
        left_type = left.type
        right_type = right.type

        # Boolean extension for both operands
        left = self._extend_boolean(builder, left, left_type)
        right = self._extend_boolean(builder, right, right_type)

        # Convert between int and float as needed
        if isinstance(left.type, ir.IntType) and isinstance(right.type, ir.FloatType):
            left = builder.sitofp(left, ir.FloatType())
        elif isinstance(left.type, ir.FloatType) and isinstance(right.type, ir.IntType):
            right = builder.sitofp(right, ir.FloatType())

        return left, right

    def _extend_boolean(self, builder, value: ir.Value, typ: ir.Type) -> ir.Value:
        # Convert i1 (bool) to i32 or float if needed
        if isinstance(typ, ir.IntType) and typ.width == 1:
            return builder.zext(value, ir.IntType(32))
        elif isinstance(typ, ir.FloatType) and isinstance(value.type, ir.IntType) and value.type.width == 1:
            value = builder.zext(value, ir.IntType(32))
            return builder.sitofp(value, ir.FloatType())
        return value

    def convert_to_int(self, builder, value: ir.Value) -> ir.Value:
        if isinstance(value.type, ir.FloatType):
            return builder.fptosi(value, ir.IntType(32))
        return value

    def convert_to_float(self, builder, value: ir.Value) -> ir.Value:
        if isinstance(value.type, ir.IntType):
            return builder.sitofp(value, ir.FloatType())
        return value