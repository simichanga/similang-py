from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Any, Union
from enum import Enum


class NodeType(Enum):
    Program = 'Program'

    # Statements
    ExpressionStatement = 'ExpressionStatement'
    LetStatement = 'LetStatement'
    FunctionStatement = 'FunctionStatement'
    BlockStatement = 'BlockStatement'
    ReturnStatement = 'ReturnStatement'
    AssignStatement = 'AssignStatement'
    IfStatement = 'IfStatement'
    WhileStatement = 'WhileStatement'
    ForStatement = 'ForStatement'
    BreakStatement = 'BreakStatement'
    ContinueStatement = 'ContinueStatement'
    StructDefinition = 'StructDefinition'
    IndexAssignStatement = 'IndexAssignStatement'
    FieldAssignStatement = 'FieldAssignStatement'

    # Expressions
    InfixExpression = 'InfixExpression'
    CallExpression = 'CallExpression'
    PrefixExpression = 'PrefixExpression'
    PostfixExpression = 'PostfixExpression'
    IndexExpression = 'IndexExpression'
    FieldAccessExpression = 'FieldAccessExpression'

    # Literals
    IntegerLiteral = 'IntegerLiteral'
    FloatLiteral = 'FloatLiteral'
    IdentifierLiteral = 'IdentifierLiteral'
    BooleanLiteral = 'BooleanLiteral'
    StringLiteral = 'StringLiteral'
    ArrayLiteral = 'ArrayLiteral'
    StructLiteral = 'StructLiteral'

    # Helper
    FunctionParameter = 'FunctionParameter'
    StructField = 'StructField'


# --- Source location ---
@dataclass
class SourceLocation:
    """Position of a node in the original source text."""
    line: int = 0         # 1-based line number
    col: int = 0          # 0-based column (position in source)
    end_line: int = 0     # 1-based end line (0 = unknown)
    end_col: int = 0      # 0-based end column (0 = unknown)

    def json(self) -> dict:
        return {'line': self.line, 'col': self.col,
                'end_line': self.end_line, 'end_col': self.end_col}

    def __bool__(self) -> bool:
        return self.line > 0

    def __repr__(self) -> str:
        return f"Loc({self.line}:{self.col})"


# --- Node base ---
@dataclass
class Node:
    def type(self) -> NodeType:
        raise NotImplementedError

    # Source location — set by the parser. Not a dataclass field so it
    # doesn't interfere with subclass __init__ signatures or json().
    @property
    def loc(self) -> SourceLocation:
        return getattr(self, '_loc', SourceLocation())

    @loc.setter
    def loc(self, value: SourceLocation) -> None:
        object.__setattr__(self, '_loc', value)

    def json(self) -> dict:
        """Return a JSON-serializable dict of the node tree."""
        def _serialize(obj: Any):
            if isinstance(obj, Node):
                return obj.json()
            if isinstance(obj, list):
                return [_serialize(x) for x in obj]
            if isinstance(obj, Enum):
                return obj.value
            return obj
        # Walk own fields (do NOT use asdict — it recursively converts Nodes to dicts)
        result: dict = {'type': self.type().value}
        for f in self.__dataclass_fields__:
            result[f] = _serialize(getattr(self, f))
        # Include source location if present
        loc = self.loc
        if loc:
            result['loc'] = loc.json()
        return result


# --- Program ---
@dataclass
class Program(Node):
    statements: List['Statement'] = field(default_factory=list)

    def type(self) -> NodeType:
        return NodeType.Program


# --- Expression / Statement base types ---
@dataclass
class Statement(Node):
    pass


@dataclass
class Expression(Node):
    pass


# --- Helper ---
@dataclass
class FunctionParameter(Expression):
    name: str
    value_type: Optional[str] = None

    def type(self) -> NodeType:
        return NodeType.FunctionParameter


# --- Statements ---
@dataclass
class ExpressionStatement(Statement):
    expr: Optional[Expression] = None

    def type(self) -> NodeType:
        return NodeType.ExpressionStatement


@dataclass
class LetStatement(Statement):
    name: Optional['IdentifierLiteral'] = None
    value: Optional[Expression] = None
    value_type: Optional[str] = None

    def type(self) -> NodeType:
        return NodeType.LetStatement


@dataclass
class BlockStatement(Statement):
    statements: List[Statement] = field(default_factory=list)

    def type(self) -> NodeType:
        return NodeType.BlockStatement


@dataclass
class ReturnStatement(Statement):
    return_value: Optional[Expression] = None

    def type(self) -> NodeType:
        return NodeType.ReturnStatement


@dataclass
class FunctionStatement(Statement):
    name: Optional['IdentifierLiteral'] = None
    parameters: List[FunctionParameter] = field(default_factory=list)
    body: Optional[BlockStatement] = None
    return_type: Optional[str] = None

    def type(self) -> NodeType:
        return NodeType.FunctionStatement


@dataclass
class AssignStatement(Statement):
    ident: Optional['IdentifierLiteral'] = None
    operator: str = ''
    right_value: Optional[Expression] = None

    def type(self) -> NodeType:
        return NodeType.AssignStatement


@dataclass
class IfStatement(Statement):
    condition: Optional[Expression] = None
    consequence: Optional[BlockStatement] = None
    alternative: Optional[BlockStatement] = None

    def type(self) -> NodeType:
        return NodeType.IfStatement


@dataclass
class WhileStatement(Statement):
    condition: Optional[Expression] = None
    body: Optional[BlockStatement] = None

    def type(self) -> NodeType:
        return NodeType.WhileStatement


@dataclass
class ForStatement(Statement):
    var_declaration: Optional[LetStatement] = None
    condition: Optional[Expression] = None
    action: Optional[Expression] = None
    body: Optional[BlockStatement] = None

    def type(self) -> NodeType:
        return NodeType.ForStatement


@dataclass
class BreakStatement(Statement):
    def type(self) -> NodeType:
        return NodeType.BreakStatement


@dataclass
class ContinueStatement(Statement):
    def type(self) -> NodeType:
        return NodeType.ContinueStatement


# --- Expressions ---
@dataclass
class InfixExpression(Expression):
    left_node: Optional[Expression] = None
    operator: str = ''
    right_node: Optional[Expression] = None

    def type(self) -> NodeType:
        return NodeType.InfixExpression


@dataclass
class CallExpression(Expression):
    function: Optional[Expression] = None
    arguments: List[Expression] = field(default_factory=list)

    def type(self) -> NodeType:
        return NodeType.CallExpression


@dataclass
class PrefixExpression(Expression):
    operator: str = ''
    right_node: Optional[Expression] = None

    def type(self) -> NodeType:
        return NodeType.PrefixExpression


@dataclass
class PostfixExpression(Expression):
    left_node: Optional[Expression] = None
    operator: str = ''

    def type(self) -> NodeType:
        return NodeType.PostfixExpression


# --- Literals ---
@dataclass
class IntegerLiteral(Expression):
    value: Optional[int] = None

    def type(self) -> NodeType:
        return NodeType.IntegerLiteral


@dataclass
class FloatLiteral(Expression):
    value: Optional[float] = None

    def type(self) -> NodeType:
        return NodeType.FloatLiteral


@dataclass
class IdentifierLiteral(Expression):
    value: Optional[str] = None

    def type(self) -> NodeType:
        return NodeType.IdentifierLiteral


@dataclass
class BooleanLiteral(Expression):
    value: Optional[bool] = None

    def type(self) -> NodeType:
        return NodeType.BooleanLiteral


@dataclass
class StringLiteral(Expression):
    value: Optional[str] = None

    def type(self) -> NodeType:
        return NodeType.StringLiteral


# --- Array & Struct nodes ---

@dataclass
class StructField(Node):
    """A single field definition inside a struct definition."""
    name: str = ''
    value_type: Optional[str] = None

    def type(self) -> NodeType:
        return NodeType.StructField


@dataclass
class StructDefinition(Statement):
    """Top-level struct type definition: struct Point { x: int, y: int }"""
    name: Optional[IdentifierLiteral] = None
    fields: List[StructField] = field(default_factory=list)

    def type(self) -> NodeType:
        return NodeType.StructDefinition


@dataclass
class ArrayLiteral(Expression):
    """Array literal expression: [1, 2, 3]"""
    elements: List[Expression] = field(default_factory=list)

    def type(self) -> NodeType:
        return NodeType.ArrayLiteral


@dataclass
class StructLiteral(Expression):
    """Struct instantiation: Point { x: 10, y: 20 }"""
    struct_name: str = ''
    field_values: List[tuple] = field(default_factory=list)  # list of (field_name, Expression)

    def type(self) -> NodeType:
        return NodeType.StructLiteral


@dataclass
class IndexExpression(Expression):
    """Array index expression: arr[0]"""
    left: Optional[Expression] = None
    index: Optional[Expression] = None

    def type(self) -> NodeType:
        return NodeType.IndexExpression


@dataclass
class FieldAccessExpression(Expression):
    """Struct field access: point.x"""
    object: Optional[Expression] = None
    field_name: str = ''

    def type(self) -> NodeType:
        return NodeType.FieldAccessExpression


@dataclass
class IndexAssignStatement(Statement):
    """Assignment to an array element: arr[0] = 42;"""
    array: Optional[Expression] = None
    index: Optional[Expression] = None
    value: Optional[Expression] = None

    def type(self) -> NodeType:
        return NodeType.IndexAssignStatement


@dataclass
class FieldAssignStatement(Statement):
    """Assignment to a struct field: point.x = 42;"""
    object: Optional[Expression] = None
    field_name: str = ''
    value: Optional[Expression] = None

    def type(self) -> NodeType:
        return NodeType.FieldAssignStatement
