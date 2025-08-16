from __future__ import annotations
from typing import Dict, Optional, Tuple
from llvmlite import ir


class TypeSystem:
    """
    Centralized canonical mapping from Similang type names to llvmlite IR types.
    Also provides helper predicates and coercion rules at the *language* level.
    """

    def __init__(self) -> None:
        # canonical IR types
        self.type_map: Dict[str, ir.Type] = {
            'int': ir.IntType(32),
            'float': ir.FloatType(),
            'bool': ir.IntType(1),
            # represent `str` as i8* (pointer to i8)
            'str': ir.PointerType(ir.IntType(8)),
            'void': ir.VoidType(),
        }

    # --- basic accessors ---
    def get_ir_type(self, name: str) -> Optional[ir.Type]:
        return self.type_map.get(name)

    def exists(self, name: str) -> bool:
        return name in self.type_map

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

    def parse_array_type(self, type_str: str) -> Tuple[str, Optional[int]] | None:
        """Parse 'int[10]' -> ('int', 10) or 'int[]' -> ('int', None)"""
        if '[' not in type_str:
            return type_str, None

        base_type, bracket_part = type_str.split('[', 1)
        size_str = bracket_part.rstrip(']')

        if size_str == '':
            return base_type, None
        return base_type, int(size_str)

    def get_array_ir_type(self, element_type: str, size: Optional[int]) -> ir.Type:
        """Get LLVM IR type for arrays"""
        elem_ir = self.get_ir_type(element_type)
        if size is None:
            # Dynamic array - use pointer to element type
            return ir.PointerType(elem_ir)
        else:
            return ir.ArrayType(elem_ir, size)

    def is_array_type(self, type_str: str) -> bool:
        """Returns True if type_str is an array type"""
        return '[' in type_str and ']' in type_str

    def get_element_type(self, array_type: str) -> str:
        """Extract element type from array type string"""
        if not self.is_array_type(array_type):
            return array_type
        return array_type.split('[')[0]
