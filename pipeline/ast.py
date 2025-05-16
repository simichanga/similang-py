from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Optional, List

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

class Node(ABC):
    def __init__(self, node_type: NodeType) -> None:
        self.node_type = node_type

    def type(self) -> NodeType:
        return self.node_type

    def json(self) -> dict:
        result = {'type': self.type().value}  # Ensure we use .value here
        for attr, value in vars(self).items():
            if attr.startswith("_"):
                continue
            if isinstance(value, Node):
                result[attr] = value.json()
            elif isinstance(value, list):
                result[attr] = [v.json() if isinstance(v, Node) else v for v in value]
            else:
                # Ensure enum values are serialized properly
                if isinstance(value, Enum):
                    result[attr] = value.value
                else:
                    result[attr] = value
        return result



class Statement(Node):
    pass

class Expression(Node):
    pass

class Program(Statement):
    def __init__(self, statements: Optional[List[Statement]] = None) -> None:
        super().__init__(NodeType.Program)
        self.statements = statements if statements is not None else []

class FunctionParameter(Expression):
    def __init__(self, name: str, value: Optional[str] = None) -> None:
        super().__init__(NodeType.FunctionParameter)
        self.name = name
        self.value = value

# region Statements
class ExpressionStatement(Statement):
    def __init__(self, expr: Optional[Expression] = None) -> None:
        super().__init__(NodeType.ExpressionStatement)
        self.expr = expr

class LetStatement(Statement):
    def __init__(self, name: Optional[Expression] = None, value: Optional[Expression] = None, value_type: Optional[str] = None) -> None:
        super().__init__(NodeType.LetStatement)
        self.name = name
        self.value = value
        self.value_type = value_type

class BlockStatement(Statement):
    def __init__(self, statements: Optional[List[Statement]] = None) -> None:
        super().__init__(NodeType.BlockStatement)
        self.statements = statements if statements is not None else []

class ReturnStatement(Statement):
    def __init__(self, return_value: Optional[Expression] = None) -> None:
        super().__init__(NodeType.ReturnStatement)
        self.return_value = return_value

class FunctionStatement(Statement):
    def __init__(
        self,
        name: Optional[Expression] = None,
        parameters: Optional[List[FunctionParameter]] = None,
        body: Optional[BlockStatement] = None,
        return_type: Optional[str] = None
    ) -> None:
        super().__init__(NodeType.FunctionStatement)
        self.name = name
        self.parameters = parameters or []
        self.body = body
        self.return_type = return_type

class AssignStatement(Statement):
    def __init__(self, ident: Optional[Expression] = None, operator: str = "", right_value: Optional[Expression] = None) -> None:
        super().__init__(NodeType.AssignStatement)
        self.ident = ident
        self.right_value = right_value
        self.operator = operator

class IfStatement(Statement):
    def __init__(
        self,
        condition: Optional[Expression] = None,
        consequence: Optional[BlockStatement] = None,
        alternative: Optional[BlockStatement] = None
    ) -> None:
        super().__init__(NodeType.IfStatement)
        self.condition = condition
        self.consequence = consequence
        self.alternative = alternative

class WhileStatement(Statement):
    def __init__(self, condition: Optional[Expression] = None, body: Optional[BlockStatement] = None) -> None:
        super().__init__(NodeType.WhileStatement)
        self.condition = condition
        self.body = body

class ForStatement(Statement):
    def __init__(
        self,
        var_declaration: Optional[LetStatement] = None,
        condition: Optional[Expression] = None,
        action: Optional[Expression] = None,
        body: Optional[BlockStatement] = None
    ) -> None:
        super().__init__(NodeType.ForStatement)
        self.var_declaration = var_declaration
        self.condition = condition
        self.action = action
        self.body = body

class BreakStatement(Statement):
    def __init__(self) -> None:
        super().__init__(NodeType.BreakStatement)

class ContinueStatement(Statement):
    def __init__(self) -> None:
        super().__init__(NodeType.ContinueStatement)
# endregion

# region Expressions
class InfixExpression(Expression):
    def __init__(self, left_node: Optional[Expression] = None, operator: str = "", right_node: Optional[Expression] = None) -> None:
        super().__init__(NodeType.InfixExpression)
        self.left_node = left_node
        self.operator = operator
        self.right_node = right_node

class CallExpression(Expression):
    def __init__(self, function: Optional[Expression] = None, arguments: Optional[List[Expression]] = None) -> None:
        super().__init__(NodeType.CallExpression)
        self.function = function
        self.arguments = arguments or []

class PrefixExpression(Expression):
    def __init__(self, operator: str = "", right_node: Optional[Expression] = None) -> None:
        super().__init__(NodeType.PrefixExpression)
        self.operator = operator
        self.right_node = right_node

class PostfixExpression(Expression):
    def __init__(self, left_node: Optional[Expression] = None, operator: str = "") -> None:
        super().__init__(NodeType.PostfixExpression)
        self.left_node = left_node
        self.operator = operator
# endregion

# region Literals
class AbstractLiteral(Expression):
    def __init__(self, value: Any = None) -> None:
        super().__init__(self.get_node_type())
        self.value = value

    @abstractmethod
    def get_node_type(self) -> NodeType:
        pass

class IntegerLiteral(AbstractLiteral):
    def get_node_type(self) -> NodeType:
        return NodeType.IntegerLiteral

class FloatLiteral(AbstractLiteral):
    def get_node_type(self) -> NodeType:
        return NodeType.FloatLiteral

class IdentifierLiteral(AbstractLiteral):
    def get_node_type(self) -> NodeType:
        return NodeType.IdentifierLiteral

class BooleanLiteral(AbstractLiteral):
    def get_node_type(self) -> NodeType:
        return NodeType.BooleanLiteral

class StringLiteral(AbstractLiteral):
    def get_node_type(self) -> NodeType:
        return NodeType.StringLiteral
# endregion
