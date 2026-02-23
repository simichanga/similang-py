"""
AST-level optimizer for Similang.

Implements a pass-manager architecture with individual optimization passes
that transform the AST before codegen.  Each pass is a subclass of
``ASTPass`` and implements ``run(program) -> program``.

Passes included:
- **ConstantFolding**: Evaluate compile-time-known arithmetic and boolean
  expressions (e.g. ``2 + 3`` → ``5``, ``!true`` → ``false``).
- **DeadCodeElimination**: Remove unreachable statements after ``return``,
  ``break``, or ``continue``; prune always-false ``if`` branches.
- **ConstantPropagation**: Track variables assigned exactly once with a
  constant value and substitute references with the constant.

The ``ASTOptimizer`` orchestrates passes and collects statistics.
"""
from __future__ import annotations
import copy
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Set, Tuple

from frontend import ast as A

logger = logging.getLogger("similang.optimizer")


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------
@dataclass
class OptStats:
    """Counters for optimizer activity."""
    constants_folded: int = 0
    dead_stmts_removed: int = 0
    constants_propagated: int = 0

    @property
    def total(self) -> int:
        return self.constants_folded + self.dead_stmts_removed + self.constants_propagated

    def merge(self, other: OptStats) -> None:
        self.constants_folded += other.constants_folded
        self.dead_stmts_removed += other.dead_stmts_removed
        self.constants_propagated += other.constants_propagated

    def __str__(self) -> str:
        parts: list[str] = []
        if self.constants_folded:
            parts.append(f"folded {self.constants_folded} constant expr(s)")
        if self.dead_stmts_removed:
            parts.append(f"removed {self.dead_stmts_removed} dead stmt(s)")
        if self.constants_propagated:
            parts.append(f"propagated {self.constants_propagated} constant(s)")
        return ", ".join(parts) if parts else "no optimizations applied"


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------
class ASTPass:
    """Base class for AST optimization passes."""
    name: str = "unnamed"

    def run(self, program: A.Program) -> Tuple[A.Program, OptStats]:
        """Return a (possibly modified) program and stats."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Constant Folding
# ---------------------------------------------------------------------------
class ConstantFolding(ASTPass):
    """
    Fold compile-time constant arithmetic, comparisons, and unary ops.

    ``2 + 3``  →  ``5``
    ``10 / 2`` →  ``5``
    ``!true``  →  ``false``
    ``-42``    →  ``IntegerLiteral(-42)``
    """
    name = "constant-folding"

    def __init__(self) -> None:
        self.stats = OptStats()

    # ---- public ----
    def run(self, program: A.Program) -> Tuple[A.Program, OptStats]:
        self.stats = OptStats()
        program.statements = [self._visit_stmt(s) for s in program.statements]
        return program, self.stats

    # ---- visitors ----
    def _visit_stmt(self, stmt: A.Statement) -> A.Statement:
        match stmt:
            case A.LetStatement():
                if stmt.value is not None:
                    stmt.value = self._visit_expr(stmt.value)
                return stmt
            case A.FunctionStatement():
                if stmt.body is not None:
                    stmt.body = self._visit_block(stmt.body)
                return stmt
            case A.BlockStatement():
                return self._visit_block(stmt)
            case A.ReturnStatement():
                if stmt.return_value is not None:
                    stmt.return_value = self._visit_expr(stmt.return_value)
                return stmt
            case A.AssignStatement():
                if stmt.right_value is not None:
                    stmt.right_value = self._visit_expr(stmt.right_value)
                return stmt
            case A.IfStatement():
                if stmt.condition is not None:
                    stmt.condition = self._visit_expr(stmt.condition)
                if stmt.consequence is not None:
                    stmt.consequence = self._visit_block(stmt.consequence)
                if stmt.alternative is not None:
                    stmt.alternative = self._visit_block(stmt.alternative)
                return stmt
            case A.WhileStatement():
                if stmt.condition is not None:
                    stmt.condition = self._visit_expr(stmt.condition)
                if stmt.body is not None:
                    stmt.body = self._visit_block(stmt.body)
                return stmt
            case A.ForStatement():
                if stmt.var_declaration is not None:
                    stmt.var_declaration = self._visit_stmt(stmt.var_declaration)
                if stmt.condition is not None:
                    stmt.condition = self._visit_expr(stmt.condition)
                if stmt.action is not None:
                    stmt.action = self._visit_expr(stmt.action)
                if stmt.body is not None:
                    stmt.body = self._visit_block(stmt.body)
                return stmt
            case A.ExpressionStatement():
                if stmt.expr is not None:
                    stmt.expr = self._visit_expr(stmt.expr)
                return stmt
            case _:
                return stmt

    def _visit_block(self, block: A.BlockStatement) -> A.BlockStatement:
        block.statements = [self._visit_stmt(s) for s in block.statements]
        return block

    def _visit_expr(self, expr: A.Expression) -> A.Expression:
        match expr:
            case A.InfixExpression():
                expr.left_node = self._visit_expr(expr.left_node) if expr.left_node else expr.left_node
                expr.right_node = self._visit_expr(expr.right_node) if expr.right_node else expr.right_node
                folded = self._try_fold_infix(expr)
                if folded is not expr:
                    self.stats.constants_folded += 1
                return folded
            case A.PrefixExpression():
                expr.right_node = self._visit_expr(expr.right_node) if expr.right_node else expr.right_node
                folded = self._try_fold_prefix(expr)
                if folded is not expr:
                    self.stats.constants_folded += 1
                return folded
            case A.CallExpression():
                expr.arguments = [self._visit_expr(a) for a in expr.arguments]
                return expr
            case _:
                return expr

    # ---- folding helpers ----
    @staticmethod
    def _is_int(node: A.Expression) -> bool:
        return isinstance(node, A.IntegerLiteral) and node.value is not None

    @staticmethod
    def _is_float(node: A.Expression) -> bool:
        return isinstance(node, A.FloatLiteral) and node.value is not None

    @staticmethod
    def _is_bool(node: A.Expression) -> bool:
        return isinstance(node, A.BooleanLiteral) and node.value is not None

    @staticmethod
    def _is_numeric(node: A.Expression) -> bool:
        return ConstantFolding._is_int(node) or ConstantFolding._is_float(node)

    def _try_fold_infix(self, expr: A.InfixExpression) -> A.Expression:
        left, right, op = expr.left_node, expr.right_node, expr.operator
        if left is None or right is None:
            return expr

        # Integer ⊕ Integer
        if self._is_int(left) and self._is_int(right):
            return self._fold_int_op(left.value, right.value, op, expr)

        # Float ⊕ Float  or  mixed int/float
        if self._is_numeric(left) and self._is_numeric(right):
            lv = float(left.value)
            rv = float(right.value)
            return self._fold_float_op(lv, rv, op, expr)

        # Bool == Bool,  Bool != Bool
        if self._is_bool(left) and self._is_bool(right) and op in ('==', '!='):
            if op == '==':
                return A.BooleanLiteral(value=(left.value == right.value))
            else:
                return A.BooleanLiteral(value=(left.value != right.value))

        return expr

    def _fold_int_op(self, lv: int, rv: int, op: str, orig: A.Expression) -> A.Expression:
        try:
            match op:
                case '+':  return A.IntegerLiteral(value=lv + rv)
                case '-':  return A.IntegerLiteral(value=lv - rv)
                case '*':  return A.IntegerLiteral(value=lv * rv)
                case '/':
                    if rv == 0:
                        return orig  # don't fold division by zero
                    return A.IntegerLiteral(value=lv // rv)
                case '%':
                    if rv == 0:
                        return orig
                    return A.IntegerLiteral(value=lv % rv)
                case '<':  return A.BooleanLiteral(value=lv < rv)
                case '<=': return A.BooleanLiteral(value=lv <= rv)
                case '>':  return A.BooleanLiteral(value=lv > rv)
                case '>=': return A.BooleanLiteral(value=lv >= rv)
                case '==': return A.BooleanLiteral(value=lv == rv)
                case '!=': return A.BooleanLiteral(value=lv != rv)
                case _:    return orig
        except Exception:
            return orig

    def _fold_float_op(self, lv: float, rv: float, op: str, orig: A.Expression) -> A.Expression:
        try:
            match op:
                case '+':  return A.FloatLiteral(value=lv + rv)
                case '-':  return A.FloatLiteral(value=lv - rv)
                case '*':  return A.FloatLiteral(value=lv * rv)
                case '/':
                    if rv == 0.0:
                        return orig
                    return A.FloatLiteral(value=lv / rv)
                case '%':
                    if rv == 0.0:
                        return orig
                    return A.FloatLiteral(value=lv % rv)
                case '<':  return A.BooleanLiteral(value=lv < rv)
                case '<=': return A.BooleanLiteral(value=lv <= rv)
                case '>':  return A.BooleanLiteral(value=lv > rv)
                case '>=': return A.BooleanLiteral(value=lv >= rv)
                case '==': return A.BooleanLiteral(value=lv == rv)
                case '!=': return A.BooleanLiteral(value=lv != rv)
                case _:    return orig
        except Exception:
            return orig

    def _try_fold_prefix(self, expr: A.PrefixExpression) -> A.Expression:
        right = expr.right_node
        if right is None:
            return expr
        if expr.operator == '-':
            if self._is_int(right):
                return A.IntegerLiteral(value=-right.value)
            if self._is_float(right):
                return A.FloatLiteral(value=-right.value)
        if expr.operator == '!':
            if self._is_bool(right):
                return A.BooleanLiteral(value=not right.value)
        return expr


# ---------------------------------------------------------------------------
# Dead Code Elimination
# ---------------------------------------------------------------------------
class DeadCodeElimination(ASTPass):
    """
    Remove unreachable code:

    - Statements after ``return``, ``break``, or ``continue`` in a block.
    - ``if`` with a constant-false condition and no else → remove entirely.
    - ``if`` with a constant-true condition → replace with the consequence block.
    - ``while(false)`` → remove entirely.
    """
    name = "dead-code-elimination"

    def __init__(self) -> None:
        self.stats = OptStats()

    def run(self, program: A.Program) -> Tuple[A.Program, OptStats]:
        self.stats = OptStats()
        program.statements = self._visit_stmts(program.statements)
        return program, self.stats

    def _visit_stmts(self, stmts: List[A.Statement]) -> List[A.Statement]:
        result: List[A.Statement] = []
        for s in stmts:
            s = self._visit_stmt(s)
            if s is None:
                continue
            result.append(s)
            # if this statement is a terminator, everything after is dead
            if isinstance(s, (A.ReturnStatement, A.BreakStatement, A.ContinueStatement)):
                removed = len(stmts) - len(result)
                if removed > 0:
                    # only count the ones not already processed
                    remaining = len(stmts) - stmts.index(s) - 1
                    self.stats.dead_stmts_removed += remaining
                break
        return result

    def _visit_stmt(self, stmt: A.Statement) -> Optional[A.Statement]:
        match stmt:
            case A.FunctionStatement():
                if stmt.body is not None:
                    stmt.body.statements = self._visit_stmts(stmt.body.statements)
                return stmt
            case A.BlockStatement():
                stmt.statements = self._visit_stmts(stmt.statements)
                return stmt
            case A.IfStatement():
                return self._visit_if(stmt)
            case A.WhileStatement():
                return self._visit_while(stmt)
            case A.ForStatement():
                if stmt.body is not None:
                    stmt.body.statements = self._visit_stmts(stmt.body.statements)
                return stmt
            case _:
                return stmt

    def _visit_if(self, stmt: A.IfStatement) -> Optional[A.Statement]:
        # Recursively optimize branches first
        if stmt.consequence is not None:
            stmt.consequence.statements = self._visit_stmts(stmt.consequence.statements)
        if stmt.alternative is not None:
            stmt.alternative.statements = self._visit_stmts(stmt.alternative.statements)

        # Check for constant condition
        if isinstance(stmt.condition, A.BooleanLiteral) and stmt.condition.value is not None:
            if stmt.condition.value:
                # always true → replace with consequence
                self.stats.dead_stmts_removed += 1
                if stmt.consequence is not None:
                    return stmt.consequence
                return None
            else:
                # always false → replace with alternative (or remove)
                self.stats.dead_stmts_removed += 1
                if stmt.alternative is not None:
                    return stmt.alternative
                return None
        return stmt

    def _visit_while(self, stmt: A.WhileStatement) -> Optional[A.Statement]:
        if stmt.body is not None:
            stmt.body.statements = self._visit_stmts(stmt.body.statements)
        # while(false) → dead
        if isinstance(stmt.condition, A.BooleanLiteral) and stmt.condition.value is False:
            self.stats.dead_stmts_removed += 1
            return None
        return stmt


# ---------------------------------------------------------------------------
# Constant Propagation
# ---------------------------------------------------------------------------
class ConstantPropagation(ASTPass):
    """
    Track variables that are assigned exactly once with a compile-time constant
    and replace later reads with that constant value.

    Limitations (intentional for safety):
    - Only propagates within a single function body.
    - Skips variables that are reassigned (via AssignStatement or postfix ++/--).
    - Skips variables used as loop counters.
    - Does not propagate across function calls.
    """
    name = "constant-propagation"

    def __init__(self) -> None:
        self.stats = OptStats()

    def run(self, program: A.Program) -> Tuple[A.Program, OptStats]:
        self.stats = OptStats()
        for stmt in program.statements:
            if isinstance(stmt, A.FunctionStatement) and stmt.body is not None:
                self._optimize_function(stmt)
        return program, self.stats

    def _optimize_function(self, func: A.FunctionStatement) -> None:
        # 1. Collect all let-bound constants in the function body
        constants: Dict[str, A.Expression] = {}
        mutated: Set[str] = set()

        self._scan_block(func.body, constants, mutated)

        # Remove any names that were mutated
        for m in mutated:
            constants.pop(m, None)

        if not constants:
            return

        # 2. Substitute identifier references
        self._substitute_block(func.body, constants)

    def _scan_block(self, block: A.BlockStatement, constants: Dict[str, A.Expression], mutated: Set[str]) -> None:
        for stmt in block.statements:
            self._scan_stmt(stmt, constants, mutated)

    def _scan_stmt(self, stmt: A.Statement, constants: Dict[str, A.Expression], mutated: Set[str]) -> None:
        match stmt:
            case A.LetStatement():
                name = stmt.name.value if stmt.name else None
                if name and stmt.value is not None and self._is_constant(stmt.value):
                    if name not in constants:
                        constants[name] = copy.deepcopy(stmt.value)
                    else:
                        # re-assigned → mark as mutated
                        mutated.add(name)
            case A.AssignStatement():
                if stmt.ident:
                    mutated.add(stmt.ident.value)
            case A.BlockStatement():
                self._scan_block(stmt, constants, mutated)
            case A.IfStatement():
                if stmt.consequence:
                    self._scan_block(stmt.consequence, constants, mutated)
                if stmt.alternative:
                    self._scan_block(stmt.alternative, constants, mutated)
            case A.WhileStatement():
                if stmt.body:
                    self._scan_block(stmt.body, constants, mutated)
                # variables used in loop body are risky
                self._collect_assigned_in_block(stmt.body, mutated)
            case A.ForStatement():
                if stmt.var_declaration and stmt.var_declaration.name:
                    mutated.add(stmt.var_declaration.name.value)
                if stmt.body:
                    self._scan_block(stmt.body, constants, mutated)
                    self._collect_assigned_in_block(stmt.body, mutated)
            case A.ExpressionStatement():
                # check for postfix ++/-- on identifiers
                if isinstance(stmt.expr, A.PostfixExpression) and isinstance(stmt.expr.left_node, A.IdentifierLiteral):
                    mutated.add(stmt.expr.left_node.value)
            case _:
                pass

    def _collect_assigned_in_block(self, block: Optional[A.BlockStatement], mutated: Set[str]) -> None:
        if block is None:
            return
        for stmt in block.statements:
            if isinstance(stmt, A.AssignStatement) and stmt.ident:
                mutated.add(stmt.ident.value)
            elif isinstance(stmt, A.ExpressionStatement):
                if isinstance(stmt.expr, A.PostfixExpression) and isinstance(stmt.expr.left_node, A.IdentifierLiteral):
                    mutated.add(stmt.expr.left_node.value)
            elif isinstance(stmt, A.BlockStatement):
                self._collect_assigned_in_block(stmt, mutated)

    @staticmethod
    def _is_constant(expr: A.Expression) -> bool:
        return isinstance(expr, (A.IntegerLiteral, A.FloatLiteral, A.BooleanLiteral, A.StringLiteral))

    def _substitute_block(self, block: A.BlockStatement, constants: Dict[str, A.Expression]) -> None:
        for i, stmt in enumerate(block.statements):
            block.statements[i] = self._substitute_stmt(stmt, constants)

    def _substitute_stmt(self, stmt: A.Statement, constants: Dict[str, A.Expression]) -> A.Statement:
        match stmt:
            case A.LetStatement():
                if stmt.value is not None:
                    stmt.value = self._substitute_expr(stmt.value, constants)
                return stmt
            case A.ReturnStatement():
                if stmt.return_value is not None:
                    stmt.return_value = self._substitute_expr(stmt.return_value, constants)
                return stmt
            case A.AssignStatement():
                if stmt.right_value is not None:
                    stmt.right_value = self._substitute_expr(stmt.right_value, constants)
                return stmt
            case A.ExpressionStatement():
                if stmt.expr is not None:
                    stmt.expr = self._substitute_expr(stmt.expr, constants)
                return stmt
            case A.IfStatement():
                if stmt.condition is not None:
                    stmt.condition = self._substitute_expr(stmt.condition, constants)
                if stmt.consequence is not None:
                    self._substitute_block(stmt.consequence, constants)
                if stmt.alternative is not None:
                    self._substitute_block(stmt.alternative, constants)
                return stmt
            case A.WhileStatement():
                if stmt.condition is not None:
                    stmt.condition = self._substitute_expr(stmt.condition, constants)
                if stmt.body is not None:
                    self._substitute_block(stmt.body, constants)
                return stmt
            case A.ForStatement():
                if stmt.condition is not None:
                    stmt.condition = self._substitute_expr(stmt.condition, constants)
                if stmt.body is not None:
                    self._substitute_block(stmt.body, constants)
                return stmt
            case A.BlockStatement():
                self._substitute_block(stmt, constants)
                return stmt
            case _:
                return stmt

    def _substitute_expr(self, expr: A.Expression, constants: Dict[str, A.Expression]) -> A.Expression:
        match expr:
            case A.IdentifierLiteral():
                if expr.value in constants:
                    self.stats.constants_propagated += 1
                    return copy.deepcopy(constants[expr.value])
                return expr
            case A.InfixExpression():
                if expr.left_node is not None:
                    expr.left_node = self._substitute_expr(expr.left_node, constants)
                if expr.right_node is not None:
                    expr.right_node = self._substitute_expr(expr.right_node, constants)
                return expr
            case A.PrefixExpression():
                if expr.right_node is not None:
                    expr.right_node = self._substitute_expr(expr.right_node, constants)
                return expr
            case A.PostfixExpression():
                # don't substitute — postfix modifies the variable
                return expr
            case A.CallExpression():
                expr.arguments = [self._substitute_expr(a, constants) for a in expr.arguments]
                return expr
            case _:
                return expr


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
class ASTOptimizer:
    """
    Run a configurable set of AST passes on a program.

    Usage::

        optimizer = ASTOptimizer(opt_level=2)
        program, stats = optimizer.optimize(program)
    """

    # Pass ordering per opt-level:
    #   0  → no passes
    #   1  → constant folding
    #   2  → constant folding → dead code elimination
    #   3  → constant propagation → constant folding → dead code elimination (iterated)
    PASS_MAP = {
        0: [],
        1: [ConstantFolding],
        2: [ConstantFolding, DeadCodeElimination],
        3: [ConstantPropagation, ConstantFolding, DeadCodeElimination],
    }

    MAX_ITERATIONS = 4  # max fixed-point iterations for O3

    def __init__(self, opt_level: int = 2) -> None:
        self.opt_level = max(0, min(opt_level, 3))
        self.stats = OptStats()

    def optimize(self, program: A.Program) -> Tuple[A.Program, OptStats]:
        """Run optimization passes and return the optimized program + stats."""
        self.stats = OptStats()
        pass_classes = self.PASS_MAP.get(self.opt_level, [])
        if not pass_classes:
            return program, self.stats

        if self.opt_level >= 3:
            # Iterate until fixed-point
            for iteration in range(self.MAX_ITERATIONS):
                round_stats = OptStats()
                for cls in pass_classes:
                    p = cls()
                    program, pstats = p.run(program)
                    round_stats.merge(pstats)
                    logger.debug("  pass %s: %s", p.name, pstats)
                self.stats.merge(round_stats)
                if round_stats.total == 0:
                    logger.debug("  fixed-point reached after %d iteration(s)", iteration + 1)
                    break
        else:
            for cls in pass_classes:
                p = cls()
                program, pstats = p.run(program)
                self.stats.merge(pstats)
                logger.debug("  pass %s: %s", p.name, pstats)

        logger.info("AST optimizer (%d passes): %s", len(pass_classes), self.stats)
        return program, self.stats
