from __future__ import annotations
from typing import Optional, Tuple, List
from llvmlite import ir

from frontend import ast as A
from middle.types import TypeSystem
from backend.llvm_init import LLVMInitializer
from backend.expr_lowerer import ExpressionLowerer
from util.env import Environment, VariableNotFoundError


class Codegen:
    """
    High-level code generator that walks top-level AST statements and emits LLVM IR using llvmlite.
    Important properties:
    - self.module: the generated module
    - self.types: TypeSystem instance (language-level)
    - self.env: Environment mapping names to (value, type_name) where value can be
               an alloca ptr for variables or an ir.Function for functions.
    """

    def __init__(self, module_name: str = "main"):
        self.module = ir.Module(module_name)
        self.types = TypeSystem()
        self.env = Environment()
        # builder is set when generating function bodies and reset after
        self.builder: Optional[ir.IRBuilder] = None
        # helper initializer declares printf and booleans
        self.llvm_init = LLVMInitializer()
        self.printf = LLVMInitializer.declare_printf(self.module)
        self.true_gv, self.false_gv = LLVMInitializer.init_booleans(self.module)
        # register builtins in env: store the printf function and booleans
        self.env.define('printf', self.printf, 'int')
        self.env.define('true', self.true_gv, 'bool')
        self.env.define('false', self.false_gv, 'bool')

        self.errors: List[str] = []
        # stacks for break/continue labels
        self._break_stack: List[ir.Block] = []
        self._continue_stack: List[ir.Block] = []

    # ---- public API ----
    def compile(self, program: A.Program) -> ir.Module:
        self.visit(program)
        return self.module

    def visit(self, node: A.Node):
        meth = getattr(self, f"visit_{node.type().name.lower()}", None)
        if meth is None:
            raise NotImplementedError(f"No codegen visitor for {node.type().name}")
        return meth(node)

    # ---- program / top-level ----
    def visit_program(self, node: A.Program) -> None:
        for stmt in node.statements:
            self.visit(stmt)

    def visit_functionstatement(self, node: A.FunctionStatement) -> None:
        if node.name is None:
            self.errors.append("Function without a name")
            return
        fname = node.name.value
        # parameter types
        param_types = [self.types.get_ir_type(p.value_type) for p in node.parameters]
        ret_type = self.types.get_ir_type(node.return_type or 'void')

        fnty = ir.FunctionType(ret_type, param_types)
        func = ir.Function(self.module, fnty, name=fname)

        # store function in env BEFORE generating body (allows recursion)
        self.env.define(fname, func, node.return_type or 'void')

        # entry block and builder
        entry = func.append_basic_block(f"{fname}_entry")
        prev_builder = self.builder
        self.builder = ir.IRBuilder(entry)

        # allocate space for parameters and store
        for i, param in enumerate(func.args):
            param_name = node.parameters[i].name
            param_type = param_types[i]
            alloca = self.builder.alloca(param_type)
            self.builder.store(param, alloca)
            self.env.define(param_name, alloca, node.parameters[i].value_type)

        # compile function body
        if node.body is not None:
            self.visit(node.body)

        # if function not terminated, add default return
        if not self.builder.block.is_terminated:
            if isinstance(ret_type, ir.IntType):
                self.builder.ret(ir.Constant(ret_type, 0))
            elif isinstance(ret_type, ir.FloatType):
                self.builder.ret(ir.Constant(ret_type, 0.0))
            elif isinstance(ret_type, ir.VoidType):
                self.builder.ret_void()
            else:
                # default to 0 for unknown integer-like types
                try:
                    self.builder.ret(ir.Constant(ret_type, 0))
                except Exception as e:
                    self.errors.append(f"Could not emit default return for function {fname}: {e}")

        # restore builder
        self.builder = prev_builder

    def visit_letstatement(self, node: A.LetStatement) -> None:
        """Enhanced to handle array types"""

        name = node.name.value
        type_name = node.value_type

        if self.types.is_array_type(type_name):
            element_type, size = self.types.parse_array_type(type_name)
            if size is not None:
                array_ir_type = self.types.get_array_ir_type(element_type, size)
            else:
                # Dynamic array
                array_ir_type = self.types.get_array_ir_type(element_type, None)
        else:
            array_ir_type = self.types.get_ir_type(type_name)

        # create alloca in current function scope (must have builder)
        if self.builder is None:
            # Global array
            if isinstance(node.value, A.ArrayLiteral):
                init_val = self._lower_array_literal(node.value, type)
            else:
                init_val = ir.Constant(array_ir_type, None)

            gvar = ir.GlobalVariable(self.module, array_ir_type, name)
            gvar.global_constant = False
            gvar.initializer = init_val
            self.env.define(name, gvar, type_name)
        else:
            # Local array
            ptr = self.builder.alloca(array_ir_type)
            if isinstance(node.value, A.ArrayLiteral):
                self._store_array_literal(node.value, ptr, type_name)
            self.env.define(name, ptr, type_name)

    def _store_array_literal(self, node: A.ArrayLiteral, array_ptr: ir.Value, expected_type: str):
        """Store array literal elements into allocated array"""
        element_type, _ = self.types.parse_array_type(expected_type)
        for i, elem in enumerate(node.elements):
            val, _ = self._lower_expression(elem)
            # Get pointer to array element
            indices = [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), i)]
            elem_ptr = self.builder.gep(array_ptr, indices)
            self.builder.store(val, elem_ptr)

    def visit_expressionstatement(self, node: A.ExpressionStatement) -> None:
        if node.expr is not None:
            # Check if the expression is actually a statement (e.g., IfStatement)
            # and handle it appropriately
            if isinstance(node.expr, A.Statement):
                # If it's a statement type, visit it as a statement instead of lowering as expression
                self.visit(node.expr)
            else:
                # Otherwise, handle as normal expression
                self._lower_expression(node.expr)
    def visit_blockstatement(self, node: A.BlockStatement) -> None:
        # new lexical scope: we rely on Environment to manage nested scopes (util/env.py)
        # simply visit all statements
        for s in node.statements:
            self.visit(s)

    def visit_returnstatement(self, node: A.ReturnStatement) -> None:
        if self.builder is None:
            self.errors.append("Return outside of function")
            return
        if node.return_value is None:
            self.builder.ret_void()
            return
        val, tname = self._lower_expression(node.return_value)
        # find current function declared return type in env? fallback: use val type
        # convert to function's expected return ir type if possible
        # We'll attempt to simply return the value (assuming sema ensured type-compatibility)
        ret_type_ir = val.type
        if isinstance(ret_type_ir, ir.FloatType) and isinstance(val.type, ir.IntType):
            # unlikely: handle basic mismatch
            val = self.builder.sitofp(val, ir.FloatType())
        self.builder.ret(val)

    def visit_assignstatement(self, node: A.AssignStatement) -> None:
        name = node.ident.value
        try:
            ptr, type_name = self.env.lookup(name)
        except VariableNotFoundError:
            self.errors.append(f"Assign to undeclared variable {name}")
            return
        right_val, right_type = self._lower_expression(node.right_value)
        # operator handling: '=', '+=', '-=', etc.
        if node.operator == '=':
            to_store = self._coerce_value_to_type(right_val, right_type, type_name)
        else:
            # load original
            orig = self.builder.load(ptr)
            # coerce both to a common numeric representation
            # prefer float if either is float
            if type_name == 'float' or right_type == 'float':
                l = orig if isinstance(orig.type, ir.FloatType) else self.builder.sitofp(orig, ir.FloatType())
                r = right_val if isinstance(right_val.type, ir.FloatType) else self.builder.sitofp(right_val, ir.FloatType())
                match node.operator:
                    case '+=': res = self.builder.fadd(l, r)
                    case '-=': res = self.builder.fsub(l, r)
                    case '*=': res = self.builder.fmul(l, r)
                    case '/=': res = self.builder.fdiv(l, r)
                    case _: 
                        self.errors.append(f"Unsupported assignment operator {node.operator}")
                        return
                to_store = self._coerce_value_to_type(res, 'float', type_name)
            else:
                # integer ops
                l = orig
                r = right_val if isinstance(right_val.type, ir.IntType) else self.builder.fptosi(right_val, ir.IntType(32))
                match node.operator:
                    case '+=': res = self.builder.add(l, r)
                    case '-=': res = self.builder.sub(l, r)
                    case '*=': res = self.builder.mul(l, r)
                    case '/=': res = self.builder.sdiv(l, r)
                    case _:
                        self.errors.append(f"Unsupported assignment operator {node.operator}")
                        return
                to_store = res
        self.builder.store(to_store, ptr)

    def visit_ifstatement(self, node: A.IfStatement) -> None:
        cond_val, cond_type = self._lower_expression(node.condition)
        # expect cond_type == 'bool'
        # create blocks
        then_bb = self.builder.append_basic_block("if_then")
        else_bb = self.builder.append_basic_block("if_else") if node.alternative else None
        cont_bb = self.builder.append_basic_block("if_cont")

        if else_bb is None:
            # conditional branch to then or continue
            self.builder.cbranch(cond_val, then_bb, cont_bb)
            # then
            self.builder.position_at_start(then_bb)
            self.visit(node.consequence)
            if not self.builder.block.is_terminated:
                self.builder.branch(cont_bb)
            # continue
            self.builder.position_at_start(cont_bb)
        else:
            self.builder.cbranch(cond_val, then_bb, else_bb)
            # then
            self.builder.position_at_start(then_bb)
            self.visit(node.consequence)
            if not self.builder.block.is_terminated:
                self.builder.branch(cont_bb)
            # else
            self.builder.position_at_start(else_bb)
            self.visit(node.alternative)
            if not self.builder.block.is_terminated:
                self.builder.branch(cont_bb)
            # continue
            self.builder.position_at_start(cont_bb)

    def visit_whilestatement(self, node: A.WhileStatement) -> None:
        # create blocks: entry, body, after
        entry = self.builder.append_basic_block("while_entry")
        body = self.builder.append_basic_block("while_body")
        after = self.builder.append_basic_block("while_after")

        # initial branch to entry
        self.builder.branch(entry)
        # entry: evaluate condition and branch
        self.builder.position_at_start(entry)
        cond_val, _ = self._lower_expression(node.condition)
        self.builder.cbranch(cond_val, body, after)
        # body
        self.builder.position_at_start(body)
        # support break/continue
        self._break_stack.append(after)
        self._continue_stack.append(entry)
        self.visit(node.body)
        # after body, branch back to entry if not terminated
        if not self.builder.block.is_terminated:
            self.builder.branch(entry)
        self._break_stack.pop()
        self._continue_stack.pop()
        # after
        self.builder.position_at_start(after)

    def visit_forstatement(self, node: A.ForStatement) -> None:
        # scope: var declaration then loop
        # create blocks
        entry = self.builder.append_basic_block("for_entry")
        body = self.builder.append_basic_block("for_body")
        after = self.builder.append_basic_block("for_after")

        # let var declaration executed before loop
        self.visit(node.var_declaration)

        # initial branch
        self.builder.branch(entry)

        # entry: evaluate condition
        self.builder.position_at_start(entry)
        if node.condition is None:
            cond_val = ir.Constant(self.types.get_ir_type('bool'), 1)  # true
        else:
            cond_val, _ = self._lower_expression(node.condition)
        self.builder.cbranch(cond_val, body, after)

        # body
        self.builder.position_at_start(body)
        self._break_stack.append(after)
        self._continue_stack.append(entry)
        self.visit(node.body)
        # action expression (usually assignment)
        if node.action is not None:
            self._lower_expression(node.action)
        if not self.builder.block.is_terminated:
            self.builder.branch(entry)
        self._break_stack.pop()
        self._continue_stack.pop()
        # after
        self.builder.position_at_start(after)

    def visit_breakstatement(self, node: A.BreakStatement) -> None:
        if not self._break_stack:
            self.errors.append("Break outside loop")
            return
        self.builder.branch(self._break_stack[-1])

    def visit_continuestatement(self, node: A.ContinueStatement) -> None:
        if not self._continue_stack:
            self.errors.append("Continue outside loop")
            return
        self.builder.branch(self._continue_stack[-1])

    # ---- helpers ----
    def _lower_expression(self, node: A.Expression) -> Tuple[ir.Value, str]:
        """
        Lower expression using ExpressionLowerer. Returns (value, type_name).
        """
        if self.builder is None:
            raise RuntimeError("Attempting to lower an expression outside of a function body (builder is None).")
        lowerer = ExpressionLowerer(self.builder, self.module, self.types, self.env)
        v, t = lowerer.lower(node)
        return v, t

    def _lower_array_literal(self, node: A.ArrayLiteral, expected_type: str) -> ir.Constant:
        """Lower array literal to LLVM constant"""
        element_type, size = self.types.parse_array_type(expected_type)
        elem_ir_type = self.types.get_ir_type(element_type)

        # Convert elements to IR constants
        ir_elements = []
        for elem in node.elements:
            val, _ = self._lower_expression(elem)
            if isinstance(val, ir.Constant):
                ir_elements.append(val)
            else:
                # For non-constant expressions, use default value
                ir_elements.append(ir.Constant(elem_ir_type, 0))

        if size and len(ir_elements) != size:
            if len(ir_elements) < size:
                zero = ir.Constant(elem_ir_type, 0)
                ir_elements.extend([zero] * (size - len(ir_elements)))
            else:
                ir_elements = ir_elements[:size]

        array_type = ir.ArrayType(elem_ir_type, len(ir_elements))
        return ir.Constant(array_type, ir_elements)

    def _coerce_value_to_type(self, val: ir.Value, from_type: str, to_type: str) -> ir.Value:
        """
        Convert `val` (with language-level type name from_type) to IR value of to_type.
        """
        if from_type == to_type:
            return val
        if from_type == 'int' and to_type == 'float':
            return self.builder.sitofp(val, ir.FloatType())
        if from_type == 'float' and to_type == 'int':
            return self.builder.fptosi(val, ir.IntType(32))
        # bool -> int promotion
        if from_type == 'bool' and to_type == 'int':
            return self.builder.zext(val, ir.IntType(32))
        # int -> bool (non-zero) convert via icmp ne, 0
        if from_type == 'int' and to_type == 'bool':
            zero = ir.Constant(ir.IntType(32), 0)
            return self.builder.icmp_signed('!=', val, zero)
        # unsupported coercion: best-effort no-op
        return val
