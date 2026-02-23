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
            'int':   TypeInfo('int',   ir.IntType(32),              4, is_numeric=True),
            'float': TypeInfo('float', ir.FloatType(),              4, is_numeric=True),
            'bool':  TypeInfo('bool',  ir.IntType(1),               1),
            'str':   TypeInfo('str',   ir.PointerType(ir.IntType(8)), 8, is_primitive=False),
            'void':  TypeInfo('void',  ir.VoidType(),               0),
        }

        # ---- Type aliases ----
        # Maps user-facing alias -> canonical name.
        # The canonical name MUST exist in self.types.
        self.aliases: Dict[str, str] = {
            # Integer aliases
            'i8':     'int',
            'i16':    'int',
            'i32':    'int',
            'i64':    'int',
            'u8':     'int',
            'u16':    'int',
            'u32':    'int',
            'u64':    'int',
            # Float aliases
            'f32':    'float',
            'f64':    'float',
            # String / char aliases
            'string': 'str',
            'char':   'int',   # char is backed by i32 (Unicode code-point)
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
        # Check direct type
        if name in self.types:
            return self.types[name]
        # Parse array types: [size]element_type
        if name.startswith('['):
            arr = self.parse_array_type(name)
            if arr:
                return self.get_array_type(arr[0], arr[1])
        return None

    @staticmethod
    def parse_array_type(name: str) -> Optional[tuple]:
        """Parse '[size]element_type' into (element_type, size) or None."""
        import re
        m = re.match(r'^\[(\d+)\](\w+)$', name)
        if m:
            return (m.group(2), int(m.group(1)))
        return None

    def is_array_type(self, name: str) -> bool:
        """Return True if name represents an array type."""
        return name.startswith('[') and self.parse_array_type(name) is not None

    def is_struct_type(self, name: str) -> bool:
        """Return True if name represents a known struct type."""
        info = self.types.get(name)
        return info is not None and info.fields is not None

    def array_element_type(self, name: str) -> Optional[str]:
        """Return the element type name of an array type, or None."""
        parsed = self.parse_array_type(name)
        return parsed[0] if parsed else None

    def array_size(self, name: str) -> Optional[int]:
        """Return the size of an array type, or None."""
        parsed = self.parse_array_type(name)
        return parsed[1] if parsed else None

    def get_struct_field_type(self, struct_type: str, field_name: str) -> Optional[str]:
        """Return the type name of a struct field, or None."""
        info = self.types.get(struct_type)
        if info is None or info.fields is None:
            return None
        field_info = info.fields.get(field_name)
        return field_info.name if field_info else None

    def get_struct_field_index(self, struct_type: str, field_name: str) -> Optional[int]:
        """Return the index of a field within a struct, or None."""
        info = self.types.get(struct_type)
        if info is None or info.fields is None:
            return None
        for idx, fname in enumerate(info.fields.keys()):
            if fname == field_name:
                return idx
        return None

    def get_struct_fields(self, struct_type: str) -> Optional[Dict[str, 'TypeInfo']]:
        """Return the fields dict of a struct type, or None."""
        info = self.types.get(struct_type)
        if info is None or info.fields is None:
            return None
        return info.fields

    def resolve_alias(self, name: str) -> str:
        """Resolve a type name through the alias table to its canonical form."""
        return self.aliases.get(name, name)

    def exists(self, name: str) -> bool:
        """Return True if *name* (or its alias) refers to a known type."""
        canonical = self.resolve_alias(name)
        if canonical in self.types:
            return True
        # Check for array types: [size]element_type
        if self.is_array_type(canonical):
            elem = self.array_element_type(canonical)
            return elem is not None and self.exists(elem)
        return False

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

    # --- predicates (resolve aliases first) ---
    def is_int(self, name: str) -> bool:
        return self.resolve_alias(name) == 'int'

    def is_float(self, name: str) -> bool:
        return self.resolve_alias(name) == 'float'

    def is_bool(self, name: str) -> bool:
        return self.resolve_alias(name) == 'bool'

    def is_str(self, name: str) -> bool:
        return self.resolve_alias(name) == 'str'

    def is_void(self, name: str) -> bool:
        return self.resolve_alias(name) == 'void'

    def is_numeric(self, name: str) -> bool:
        return self.resolve_alias(name) in ('int', 'float')

    # --- coercion & assignment rules (language-level type names) ---
    def can_assign(self, target: str, source: str) -> bool:
        """
        Returns True if a value of type `source` can be assigned to `target`
        (either exact type equality or allowed implicit coercion).
        Aliases are resolved before comparison.
        """
        t = self.resolve_alias(target)
        s = self.resolve_alias(source)
        if t == s:
            return True
        if self.is_float(t) and self.is_int(s):
            return True  # widen int -> float
        if self.is_int(t) and self.is_float(s):
            return True  # narrowing allowed (backend will fptosi)
        # Array assignment: must match exactly (element type + size)
        if self.is_array_type(t) and self.is_array_type(s):
            return t == s
        # Struct assignment: must match exactly
        if self.is_struct_type(t) and self.is_struct_type(s):
            return t == s
        # bool <-> numeric? not implicitly allowed
        return False

    def binary_result_type(self, left: str, right: str, operator: str) -> Optional[str]:
        """
        Given two operand type names and an operator, return resulting type name
        for expressions like left <op> right, or None if invalid.
        Comparison operators return 'bool'.
        Arithmetic: int/int -> int, float/float -> float, int/float -> float (widen).
        Aliases are resolved before comparison.
        """
        left = self.resolve_alias(left)
        right = self.resolve_alias(right)

        # comparisons produce bool
        if operator in ('==', '!=', '<', '<=', '>', '>='):
            if (self.is_numeric(left) and self.is_numeric(right)) or (left == right):
                return 'bool'
            return None

        # arithmetic operators
        if operator in ('+', '-', '*', '/', '%', '^'):
            if self.is_numeric(left) and self.is_numeric(right):
                if left == 'float' or right == 'float':
                    return 'float'
                return 'int'
            if operator == '+' and left == 'str' and right == 'str':
                return 'str'
            return None

        # boolean NOT / unary are handled elsewhere
        return None
