from __future__ import annotations
from dataclasses import dataclass, field, asdict
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

    # Expressions
    InfixExpression = 'InfixExpression'
    CallExpression = 'CallExpression'
    PrefixExpression = 'PrefixExpression'
    PostfixExpression = 'PostfixExpression'

    # Literals
    IntegerLiteral = 'IntegerLiteral'
    FloatLiteral = 'FloatLiteral'
    IdentifierLiteral = 'IdentifierLiteral'
    BooleanLiteral = 'BooleanLiteral'
    StringLiteral = 'StringLiteral'

    # Helper
    FunctionParameter = 'FunctionParameter'


# --- Node base ---
@dataclass
class Node:
    def type(self) -> NodeType:
        raise NotImplementedError

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
        # use asdict but convert Node children recursively
        raw = asdict(self)
        return {'type': self.type().value, **{k: _serialize(v) for k, v in raw.items()}}


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
