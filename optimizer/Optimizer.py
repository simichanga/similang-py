from AST import AbstractLiteral
from __imports__ import *

class Optimizer:
    @staticmethod
    def optimize(entry_node: Program) -> Program:
        for function_statements in entry_node.statements:
            for node in function_statements.body.statements:
                # print(f"{node.json()}")
                # Check if the node is a LetStatement
                if node.type() is NodeType.LetStatement:
                    # Check if the value of the LetStatement is an InfixExpression
                    if isinstance(node.value, InfixExpression):
                        # Perform constant folding on the value
                        folded_value = Optimizer.__fold_constants(node.value)
                        # Replace the value of the LetStatement with the folded result
                        node.value = folded_value
        return entry_node

    @staticmethod
    def __fold_constants(node: InfixExpression) -> IntegerLiteral | FloatLiteral:
        """
        Evaluates a constant infix expression. Assumes both sides are constants.
        """
        # TODO refactor all this bullshit, rn tho I'm happy it works
        # TODO implement prefix folding too

        if isinstance(node.left_node, InfixExpression):
            left = Optimizer.__fold_constants(node.left_node).value
        else:
            left = node.left_node.value

        if isinstance(node.right_node, InfixExpression):
            right = Optimizer.__fold_constants(node.right_node).value
        else:
            right = node.right_node.value

        result = None
        if node.operator == "+":
            result = left + right
        elif node.operator == "-":
            result = left - right
        elif node.operator == "*":
            result = left * right
        elif node.operator == "/":
            if right == 0:
                raise ZeroDivisionError("Division by zero in constant folding")
            result = left / right
        elif node.operator == "%":
            result = left % right
        else:
            raise ValueError(f"Unsupported operator: {node.operator}")

        # Return a new literal node of the same type as the operands

        # TODO proper return type
        return IntegerLiteral(result)

    @staticmethod
    def __fold_prefix(node: PrefixExpression) -> AbstractLiteral:
        """
        Evaluates a constant prefix expression.
        """
        value = node.right_node.value

        if node.operator == "-":
            return IntegerLiteral(-value)
        elif node.operator == "!":
            return IntegerLiteral(not value)

        raise ValueError(f"Unsupported prefix operator: {node.operator}")
