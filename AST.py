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
    node_type: NodeType  # Define node type at the class level

    def type(self) -> NodeType:
        return self.node_type

    def json(self) -> dict:
        result = {'type': self.type().value}
        for attr, value in vars(self).items():
            if attr.startswith("_"):
                continue
            if isinstance(value, Node):
                result[attr] = value.json()
            elif isinstance(value, list):
                result[attr] = [v.json() if isinstance(v, Node) else v for v in value]
            else:
                result[attr] = value
        return result

class Statement(Node):
    pass

class Expression(Node):
    pass

class Program(Node):
    def __init__(self) -> None:
        self.statements: List[Statement] = []

    def type(self) -> NodeType:
        return NodeType.Program

# region Helpers
class FunctionParameter(Expression):
    def __init__(self, name: str, value: Optional[str] = None) -> None:
        self.name = name
        self.value = value

    def type(self) -> NodeType:
        return NodeType.FunctionParameter
# endregion

# region Statements
class ExpressionStatement(Statement):
    def __init__(self, expr: Expression = None) -> None:
        self.expr: Expression = expr

    def type(self) -> NodeType:
        return NodeType.ExpressionStatement

class LetStatement(Statement):
    def __init__(self, name: Expression = None, value: Expression = None, value_type: Optional[str] = None) -> None:
        self.name = name
        self.value = value
        self.value_type = value_type

    def type(self) -> NodeType:
        return NodeType.LetStatement

class BlockStatement(Statement):
    def __init__(self, statements: Optional[List[Statement]] = None) -> None:
        self.statements = statements if statements is not None else []

    def type(self) -> NodeType:
        return NodeType.BlockStatement

class ReturnStatement(Statement):
    def __init__(self, return_value: Expression) -> None:
        self.return_value = return_value

    def type(self) -> NodeType:
        return NodeType.ReturnStatement

class FunctionStatement(Statement):
    def __init__(
        self,
        name: Expression = None, # TODO refactor this later on in the parser
        parameters: Optional[List[FunctionParameter]] = None,
        body: Optional[BlockStatement] = None,
        return_type: Optional[str] = None
    ) -> None:
        self.name = name
        self.parameters = parameters or []
        self.body = body
        self.return_type = return_type

    def type(self) -> NodeType:
        return NodeType.FunctionStatement

class AssignStatement(Statement):
    def __init__(self, ident: Expression, operator: str = "", right_value: Expression = None) -> None:
        self.ident = ident
        self.right_value = right_value
        self.operator = operator

    def type(self) -> NodeType:
        return NodeType.AssignStatement

class IfStatement(Statement):
    def __init__(
        self,
        condition: Expression,
        consequence: BlockStatement,
        alternative: Optional[BlockStatement] = None
    ) -> None:
        self.condition = condition
        self.consequence = consequence
        self.alternative = alternative

    def type(self) -> NodeType:
        return NodeType.IfStatement

class WhileStatement(Statement):
    def __init__(self, condition: Expression, body: BlockStatement) -> None:
        self.condition = condition
        self.body = body

    def type(self) -> NodeType:
        return NodeType.WhileStatement

class ForStatement(Statement):
    def __init__(
        self,
        var_declaration: LetStatement | None = None,
        condition: Expression | None = None,
        action: Expression | None = None,
        body: BlockStatement | None = None
    ) -> None:
        self.var_declaration = var_declaration
        self.condition = condition
        self.action = action
        self.body = body

    def type(self) -> NodeType:
        return NodeType.ForStatement

class BreakStatement(Statement):
    def __init__(self) -> None:
        pass

    def type(self) -> NodeType:
        return NodeType.BreakStatement

class ContinueStatement(Statement):
    def __init__(self) -> None:
        pass

    def type(self) -> NodeType:
        return NodeType.ContinueStatement
# endregion

# region Expressions
class InfixExpression(Expression):
    def __init__(self, left_node: Expression, operator: str, right_node: Optional[Expression] = None) -> None:
        self.left_node: Expression = left_node
        self.operator: str = operator
        self.right_node: Expression = right_node

    def type(self) -> NodeType:
        return NodeType.InfixExpression

class CallExpression(Expression):
    def __init__(self, function: Expression = None, arguments: Optional[List[Expression]] = None) -> None:
        self.function = function
        self.arguments = arguments or []

    def type(self) -> NodeType:
        return NodeType.CallExpression
# endregion

# region Literals
class AbstractLiteral(Expression):
    def __init__(self, value: Any = None) -> None:
        self.value = value

    @abstractmethod
    def type(self) -> NodeType:
        self.node_type

class PrefixExpression(Expression):
    def __init__(self, operator: str, right_node: Expression = None) -> None:
        self.operator = operator
        self.right_node = right_node

    def type(self) -> NodeType:
        return NodeType.PrefixExpression

class PostfixExpression(Expression):
    def __init__(self, left_node: Expression, operator: str) -> None:
        self.left_node = left_node
        self.operator = operator

    def type(self) -> NodeType:
        return NodeType.PostfixExpression

class IntegerLiteral(AbstractLiteral):
    def type(self) -> NodeType:
        return NodeType.IntegerLiteral

class FloatLiteral(AbstractLiteral):
    def type(self) -> NodeType:
        return NodeType.FloatLiteral

class IdentifierLiteral(AbstractLiteral):
    def type(self) -> NodeType:
        return NodeType.IdentifierLiteral

class BooleanLiteral(AbstractLiteral):
    def type(self) -> NodeType:
        return NodeType.BooleanLiteral

class StringLiteral(AbstractLiteral):
    def type(self) -> NodeType:
        return NodeType.StringLiteral
# endregion
