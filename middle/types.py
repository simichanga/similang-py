from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from llvmlite import ir

@dataclass
class TypeInfo:
    """Rich type information."""
    name: str
    ir_type: ir.Type
    size: int  # in bytes
    is_primitive: bool = True
    is_numeric: bool = False
    is_signed: bool = True
    element_type: Optional['TypeInfo'] = None  # for arrays/pointers
    fields: Optional[Dict[str, 'TypeInfo']] = None  # for structs

class TypeSystem:
    """
    Centralized canonical mapping from Similang type names to llvmlite IR types.
    Also provides helper predicates and coercion rules at the *language* level.
    Enhanced type system with support for complex types.
    """

    def __init__(self) -> None:
        # Initialize primitive types with rich metadata
        self.types: Dict[str, TypeInfo] = {
            'int': TypeInfo('int', ir.IntType(32), 4, is_numeric=True),
            'float': TypeInfo('float', ir.FloatType(), 4, is_numeric=True),
            'bool': TypeInfo('bool', ir.IntType(1), 1),
            'str': TypeInfo('str', ir.PointerType(ir.IntType(8)), 8, is_primitive=False),
            'void': TypeInfo('void', ir.VoidType(), 0),
        }

        # Support for type aliases
        self.aliases: Dict[str, str] = {
            'i32': 'int',
            'f32': 'float',
            'string': 'str',
        }

        # Cached array types
        self._array_cache: Dict[tuple, TypeInfo] = {}

    # --- basic accessors ---
    def get_ir_type(self, name: str) -> Optional[ir.Type]:
        """Get LLVM IR type (backward compatibility)."""
        info = self.get_type_info(name)
        return info.ir_type if info else None

    def get_array_type(self, element_type: str, size: int) -> TypeInfo:
        """Create or retrieve array type."""
        cache_key = (element_type, size)
        if cache_key in self._array_cache:
            return self._array_cache[cache_key]

        elem_info = self.get_type_info(element_type)
        if not elem_info:
            raise ValueError(f"Unknown element type: {element_type}")

        ir_array = ir.ArrayType(elem_info.ir_type, size)
        array_info = TypeInfo(
            name=f"[{size}]{element_type}",
            ir_type=ir_array,
            size=elem_info.size * size,
            is_primitive=False,
            element_type=elem_info
        )
        self._array_cache[cache_key] = array_info
        return array_info

    def get_type_info(self, name: str) -> Optional[TypeInfo]:
        """Get complete type information."""
        # Resolve aliases
        if name in self.aliases:
            name = self.aliases[name]
        return self.types.get(name)

    def exists(self, name: str) -> bool:
        return name in self.types

    # --- accessors & helper ---
    def create_struct_type(self, name: str, fields: Dict[str, str]) -> TypeInfo:
        """Create a new struct type."""
        field_infos = {}
        ir_fields = []
        total_size = 0

        for field_name, field_type in fields.items():
            info = self.get_type_info(field_type)
            if not info:
                raise ValueError(f"Unknown field type: {field_type}")
            field_infos[field_name] = info
            ir_fields.append(info.ir_type)
            total_size += info.size

        ir_struct = ir.LiteralStructType(ir_fields)
        struct_info = TypeInfo(
            name=name,
            ir_type=ir_struct,
            size=total_size,
            is_primitive=False,
            fields=field_infos
        )
        self.types[name] = struct_info
        return struct_info

    def can_implicit_cast(self, from_type: str, to_type: str) -> bool:
        """Check if implicit cast is allowed."""
        if from_type == to_type:
            return True

        from_info = self.get_type_info(from_type)
        to_info = self.get_type_info(to_type)

        if not from_info or not to_info:
            return False

        # Allow numeric promotions
        if from_info.is_numeric and to_info.is_numeric:
            # int -> float is always safe
            if from_type == 'int' and to_type == 'float':
                return True
            # float -> int requires explicit cast
            return False

        return False

    # --- predicates ---
    def is_int(self, name: str) -> bool:
        return name == 'int'

    def is_float(self, name: str) -> bool:
        return name == 'float'

    def is_bool(self, name: str) -> bool:
        return name == 'bool'

    def is_str(self, name: str) -> bool:
        return name == 'str'

    def is_void(self, name: str) -> bool:
        return name == 'void'

    def is_numeric(self, name: str) -> bool:
        return name in ('int', 'float')

    # --- coercion & assignment rules (language-level type names) ---
    def can_assign(self, target: str, source: str) -> bool:
        """
        Returns True if a value of type `source` can be assigned to `target`
        (either exact type equality or allowed implicit coercion).
        We allow implicit int -> float promotion. Assigning float -> int is allowed
        but it's considered a narrowing conversion (sema may warn; here we accept).
        """
        if target == source:
            return True
        if self.is_float(target) and self.is_int(source):
            return True  # widen int -> float
        if self.is_int(target) and self.is_float(source):
            return True  # narrowing allowed (backend will fptosi)
        # bool <-> numeric? not implicitly allowed
        return False

    def binary_result_type(self, left: str, right: str, operator: str) -> Optional[str]:
        """
        Given two operand type names and an operator, return resulting type name
        for expressions like left <op> right, or None if invalid.
        Comparison operators return 'bool'.
        Arithmetic: int/int -> int, float/float -> float, int/float -> float (widen).
        """
        # comparisons produce bool
        if operator in ('==', '!=', '<', '<=', '>', '>='):
            # ensure operands are comparable
            if (self.is_numeric(left) and self.is_numeric(right)) or (left == right):
                return 'bool'
            return None

        # arithmetic operators
        if operator in ('+', '-', '*', '/', '%', '^'):
            # numeric arithmetic only
            if self.is_numeric(left) and self.is_numeric(right):
                if left == 'float' or right == 'float':
                    return 'float'
                return 'int'
            # allow string concatenation with + (if both str)
            if operator == '+' and left == 'str' and right == 'str':
                return 'str'
            return None

        # boolean NOT / unary are handled elsewhere
        return None
