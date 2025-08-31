from __future__ import annotations
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass

from frontend import ast as A
from middle.types import TypeSystem


@dataclass
class SymbolInfo:
    name: str
    type_name: str
    is_function: bool = False
    param_types: Optional[List[str]] = None
    return_type: Optional[str] = None


class SemanticAnalyzer:
    """
    Performs name resolution and basic type checking.
    - Builds nested scopes for variables and functions
    - Verifies assignments and expressions type-correctness using TypeSystem
    - Annotates AST nodes with `inferred_type` (language-level type name string)
    - Collects errors in self.errors (doesn't raise)
    """

    def __init__(self, types: Optional[TypeSystem] = None) -> None:
        self.types = types or TypeSystem()
        self.errors: List[str] = []
        # stack of scopes (each is a dict name -> SymbolInfo)
        self.scopes: List[Dict[str, SymbolInfo]] = [{}]
        # current function return type name (while analyzing function body)
        self._current_fn_ret: Optional[str] = None

    # ---- scopes ----
    def _enter_scope(self) -> None:
        self.scopes.append({})

    def _leave_scope(self) -> None:
        self.scopes.pop()

    def _define(self, sym: SymbolInfo) -> None:
        self.scopes[-1][sym.name] = sym

    def _lookup(self, name: str) -> Optional[SymbolInfo]:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    # ---- top-level API ----
    def analyze(self, program: A.Program) -> Tuple[bool, List[str]]:
        """Analyze program AST. Returns (success, errors)."""
        self.errors.clear()
        # Pre-declare builtin functions / constants if desired
        self._define(SymbolInfo(name='printf', type_name='int', is_function=True, param_types=None, return_type='int'))
        self._define(SymbolInfo(name='true', type_name='bool'))
        self._define(SymbolInfo(name='false', type_name='bool'))

        self._visit_program(program)
        return (len(self.errors) == 0), self.errors

    # ---- visitors ----
    def _visit_program(self, node: A.Program) -> None:
        for stmt in node.statements:
            self._visit_statement(stmt)

    def _visit_statement(self, node: A.Statement) -> None:
        meth = getattr(self, f"_visit_{node.type().name.lower()}", None)
        if meth is None:
            # unknown statement type -> skip for now
            return
        return meth(node)  # type: ignore[return-value]

    def _visit_expression(self, node: A.Expression) -> Optional[str]:
        meth = getattr(self, f"_visit_{node.type().name.lower()}", None)
        if meth is None:
            self.errors.append(f"Internal: no sema handler for expression {node.type().name}")
            return None
        return meth(node)  # type: ignore[return-value]

    # --- statement handlers ---
    def _visit_expressionstatement(self, node: A.ExpressionStatement) -> None:
        if node.expr is None:
            return
        t = self._visit_expression(node.expr)
        setattr(node, "inferred_type", t)

    def _visit_letstatement(self, node: A.LetStatement) -> None:
        if node.name is None:
            self.errors.append("Let statement without a name")
            return
        if node.value_type is None:
            self.errors.append(f"Let {node.name.value!r}: missing type annotation")
            return
        if not self.types.exists(node.value_type):
            self.errors.append(f"Unknown type '{node.value_type}' for variable '{node.name.value}'")
            return

        # evaluate initializer
        if node.value is None:
            self.errors.append(f"Variable '{node.name.value}' requires an initializer")
            return

        expr_type = self._visit_expression(node.value)
        if expr_type is None:
            return

        # check assignment compatibility
        if not self.types.can_assign(node.value_type, expr_type):
            self.errors.append(f"Type error: cannot assign {expr_type} to {node.value_type} (variable '{node.name.value}')")
            return

        # define variable in current scope
        self._define(SymbolInfo(name=node.name.value, type_name=node.value_type))
        setattr(node, "inferred_type", node.value_type)

    def _visit_assignstatement(self, node: A.AssignStatement) -> None:
        if node.ident is None:
            self.errors.append("Assignment missing identifier")
            return
        sym = self._lookup(node.ident.value)
        if sym is None:
            self.errors.append(f"Undeclared identifier '{node.ident.value}'")
            return

        rhs_type = self._visit_expression(node.right_value) if node.right_value is not None else None
        if rhs_type is None:
            return

        # operator-specific checks could go here (+= etc.)
        if not self.types.can_assign(sym.type_name, rhs_type):
            self.errors.append(f"Type error: cannot assign {rhs_type} to {sym.type_name} in assignment to '{node.ident.value}'")
            return
        setattr(node, "inferred_type", sym.type_name)

    def _visit_functionstatement(self, node: A.FunctionStatement) -> None:
        if node.name is None:
            self.errors.append("Function without a name")
            return
        ret_type = node.return_type or 'void'
        if not self.types.exists(ret_type):
            self.errors.append(f"Function {node.name.value!r} has unknown return type '{ret_type}'")
            return

        # parameter types
        param_types: List[str] = []
        for p in node.parameters:
            if p.value_type is None:
                self.errors.append(f"Parameter '{p.name}' in function '{node.name.value}' missing type")
                return
            if not self.types.exists(p.value_type):
                self.errors.append(f"Parameter '{p.name}' in function '{node.name.value}' has unknown type '{p.value_type}'")
                return
            param_types.append(p.value_type)

        # register function symbol in the current (outer) scope
        self._define(SymbolInfo(name=node.name.value, type_name='function', is_function=True, param_types=param_types, return_type=ret_type))

        # analyze function body in new scope
        self._enter_scope()
        # define parameters as local variables
        for p, tname in zip(node.parameters, param_types):
            self._define(SymbolInfo(name=p.name, type_name=tname))

        # set current function return type for checking return statements
        prev_ret = self._current_fn_ret
        self._current_fn_ret = ret_type

        if node.body is not None:
            self._visit_blockstatement(node.body)

        self._current_fn_ret = prev_ret
        self._leave_scope()
        setattr(node, "inferred_type", f"fn({','.join(param_types)})->{ret_type}")

    def _visit_returnstatement(self, node: A.ReturnStatement) -> None:
        if self._current_fn_ret is None:
            self.errors.append("Return statement outside of a function")
            return
        if node.return_value is None:
            # returning nothing -> ok only if current fn returns void
            if self._current_fn_ret != 'void':
                self.errors.append(f"Return missing value in function expecting {self._current_fn_ret}")
            return
        rv_type = self._visit_expression(node.return_value)
        if rv_type is None:
            return
        if not self.types.can_assign(self._current_fn_ret, rv_type):
            self.errors.append(f"Return type mismatch: function expects {self._current_fn_ret} but returned {rv_type}")

    def _visit_blockstatement(self, node: A.BlockStatement) -> None:
        self._enter_scope()
        for s in node.statements:
            self._visit_statement(s)
        self._leave_scope()

    def _visit_ifstatement(self, node: A.IfStatement) -> None:
        cond_type = self._visit_expression(node.condition) if node.condition is not None else None
        if cond_type is None:
            return
        if not self.types.is_bool(cond_type):
            self.errors.append(f"If-condition must be bool, got {cond_type}")
        if node.consequence is not None:
            self._visit_blockstatement(node.consequence)
        if node.alternative is not None:
            self._visit_blockstatement(node.alternative)

    def _visit_whilestatement(self, node: A.WhileStatement) -> None:
        cond_type = self._visit_expression(node.condition) if node.condition is not None else None
        if cond_type is None:
            return
        if not self.types.is_bool(cond_type):
            self.errors.append(f"While-condition must be bool, got {cond_type}")
        if node.body is not None:
            self._visit_blockstatement(node.body)

    def _visit_forstatement(self, node: A.ForStatement) -> None:
        # var declaration
        self._enter_scope()
        if node.var_declaration is not None:
            self._visit_letstatement(node.var_declaration)
        # condition
        if node.condition is not None:
            cond = self._visit_expression(node.condition)
            if cond is not None and not self.types.is_bool(cond):
                self.errors.append(f"For-condition must be bool, got {cond}")
        # action (assignment or expression)
        if node.action is not None:
            # action is an expression (often an AssignStatement disguised) - visit it as expr/statement
            if isinstance(node.action, A.AssignStatement):
                self._visit_assignstatement(node.action)
            else:
                self._visit_expression(node.action)
        # body
        if node.body is not None:
            self._visit_blockstatement(node.body)
        self._leave_scope()

    def _visit_breakstatement(self, node: A.BreakStatement) -> None:
        # handled in codegen; sema can't check loop-context easily here
        return

    def _visit_continuestatement(self, node: A.ContinueStatement) -> None:
        return

    # --- expression handlers ---
    def _visit_integerliteral(self, node: A.IntegerLiteral) -> Optional[str]:
        return 'int'

    def _visit_floatliteral(self, node: A.FloatLiteral) -> Optional[str]:
        return 'float'

    def _visit_stringliteral(self, node: A.StringLiteral) -> Optional[str]:
        return 'str'

    def _visit_booleanliteral(self, node: A.BooleanLiteral) -> Optional[str]:
        return 'bool'

    def _visit_identifierliteral(self, node: A.IdentifierLiteral) -> Optional[str]:
        sym = self._lookup(node.value)
        if sym is None:
            self.errors.append(f"Undeclared identifier '{node.value}'")
            return None
        return sym.type_name

    def _visit_infixexpression(self, node: A.InfixExpression) -> Optional[str]:
        left = self._visit_expression(node.left_node) if node.left_node is not None else None
        right = self._visit_expression(node.right_node) if node.right_node is not None else None
        if left is None or right is None:
            return None

        # handle assignment-like operators if used as infix (+= etc.) — treat as arithmetic
        res = self.types.binary_result_type(left, right, node.operator)
        if res is None:
            self.errors.append(f"Type error: cannot apply operator '{node.operator}' to {left} and {right}")
            return None
        setattr(node, "inferred_type", res)
        return res

    def _visit_callexpression(self, node: A.CallExpression) -> Optional[str]:
        # function must be an identifier (builtins like printf) or a function symbol
        if not isinstance(node.function, A.IdentifierLiteral):
            self.errors.append("Call expression: function must be identifier")
            return None
        fname = node.function.value
        sym = self._lookup(fname)
        if sym is None or not sym.is_function:
            self.errors.append(f"Call to unknown function '{fname}'")
            return None

        # check arity if param_types declared
        arg_types = []
        for arg in node.arguments:
            t = self._visit_expression(arg)
            if t is None:
                return None
            arg_types.append(t)

        if sym.param_types is not None:
            if len(arg_types) != len(sym.param_types):
                self.errors.append(f"Function '{fname}' expects {len(sym.param_types)} args, got {len(arg_types)}")
            else:
                for expected, given in zip(sym.param_types, arg_types):
                    if not self.types.can_assign(expected, given):
                        self.errors.append(f"Function call '{fname}': argument type mismatch, expected {expected}, got {given}")
        # returns sym.return_type or 'int' for printf fallback
        ret = sym.return_type or 'int'
        setattr(node, "inferred_type", ret)
        return ret

    def _visit_postfixexpression(self, node: A.PostfixExpression) -> Optional[str]:
        # left must be identifier and numeric
        left = node.left_node
        if not isinstance(left, A.IdentifierLiteral):
            self.errors.append("Postfix ++/-- must operate on an identifier")
            return None
        sym = self._lookup(left.value)
        if sym is None:
            self.errors.append(f"Undeclared identifier '{left.value}' in postfix")
            return None
        if not self.types.is_numeric(sym.type_name):
            self.errors.append(f"Postfix increment/decrement requires numeric type, got {sym.type_name}")
            return None
        # store inferred type on node
        setattr(node, "inferred_type", sym.type_name)
        return sym.type_name

    def _visit_prefixexpression(self, node: A.PrefixExpression) -> Optional[str]:
        # unary - : numeric -> numeric; ! : bool -> bool
        right = self._visit_expression(node.right_node) if node.right_node is not None else None
        if right is None:
            return None
        if node.operator == '-':
            if not self.types.is_numeric(right):
                self.errors.append(f"Unary - expects numeric operand, got {right}")
                return None
            return right
        if node.operator == '!':
            if not self.types.is_bool(right):
                self.errors.append(f"Unary ! expects bool operand, got {right}")
                return None
            return 'bool'
        self.errors.append(f"Unknown prefix operator {node.operator}")
        return None
