from typing import List, Optional, Tuple
from llvmlite import ir

from pipeline.environment import Environment
from pipeline.ast import (
    Program, ExpressionStatement, LetStatement, FunctionStatement, ReturnStatement,
    BlockStatement, AssignStatement, IfStatement, WhileStatement, ForStatement,
    BreakStatement, ContinueStatement, Expression, FunctionParameter, IntegerLiteral, FloatLiteral, IdentifierLiteral,
    BooleanLiteral, StringLiteral
)
from pipeline.compilation_unit.helper_methods import HelperMethods

class StatementVisitor:
    def __init__(self, compiler):
        self.compiler = compiler

    def visit_program(self, node: Program) -> None:
        for stmt in node.statements:
            self.compiler.compile(stmt)

    def visit_expression_statement(self, node: ExpressionStatement) -> None:
        self.compiler.compile(node.expr)

    def visit_let_statement(self, node: LetStatement) -> None:
        if node.name is None:
            raise ValueError("Function statement requires a valid name.")

        name: str = node.name.value
        value: Expression = node.value
        value_type = node.value_type  # TODO implement when actually doing type checking

        value, Type = self.compiler.__resolve_value(node=value)

        if self.compiler.env.lookup(name) is None:
            # Define and allocate the variable
            if value_type == 'bool':  # TODO ugly hotfix for bool assignment
                ptr = self.compiler.builder.alloca(ir.IntType(1))  # Allocate i1 type for boolean
            else:
                ptr = self.compiler.builder.alloca(Type)

            # Store the value at the ptr
            self.compiler.builder.store(value, ptr)

            # Add the value to the env
            self.compiler.env.define(name, ptr, Type)
        else:
            ptr, _ = self.compiler.env.lookup(name)
            self.compiler.builder.store(value, ptr)

    def visit_block_statement(self, node: BlockStatement) -> None:
        for stmt in node.statements:
            self.compiler.compile(stmt)

    def visit_return_statement(self, node: ReturnStatement) -> None:
        return_value, return_type = self.compiler.__resolve_value(node.return_value)

        # Ensure the return type matches the function's return type
        if isinstance(return_type, ir.FloatType) and self.compiler.type_map['float'] != return_type:
            return_value = self.compiler.builder.sitofp(return_value, ir.FloatType())
            return_type = self.compiler.type_map['float']
        elif isinstance(return_type, ir.IntType) and self.compiler.type_map['int'] != return_type:
            return_value = self.compiler.builder.sitofp(return_value, ir.FloatType())
            return_type = self.compiler.type_map['float']

        self.compiler.builder.ret(return_value)

    def visit_function_statement(self, node: FunctionStatement) -> None:
        name: str = node.name.value
        body: BlockStatement = node.body
        params: List[FunctionParameter] = node.parameters

        param_names: List[str] = [p.name for p in params]
        param_types: List[ir.Type] = [self.compiler.type_map[p.value_type] for p in params]

        return_type: ir.Type = self.compiler.type_map[node.return_type]

        fnty: ir.FunctionType = ir.FunctionType(return_type, param_types)
        func: ir.Function = ir.Function(self.compiler.module, fnty, name=name)

        block: ir.Block = func.append_basic_block(f'{name}_entry')

        previous_builder = self.compiler.builder
        self.compiler.builder = ir.IRBuilder(block)

        # Storing pointers for each parameter
        params_ptr = []
        for i, typ in enumerate(param_types):
            ptr = self.compiler.builder.alloca(typ)
            self.compiler.builder.store(func.args[i], ptr)
            params_ptr.append(ptr)

        # Adding the parameters to the env
        previous_env = self.compiler.env
        self.compiler.env = Environment(parent=self.compiler.env)
        for i, x in enumerate(zip(param_types, param_names)):
            typ = param_types[i]
            ptr = params_ptr[i]

            self.compiler.env.define(x[1], ptr, typ)

        self.compiler.env.define(name, func, return_type)

        self.compiler.compile(body)

        # Set default return type for main
        if name == 'main' and not self.compiler.builder.block.is_terminated:
            if return_type == ir.IntType(32):
                self.compiler.builder.ret(ir.Constant(ir.IntType(32), 0))
            elif return_type == ir.FloatType():
                self.compiler.builder.ret(ir.Constant(ir.FloatType(), 0))
            elif return_type == ir.VoidType():
                self.compiler.builder.ret_void()
            else:
                raise TypeError(f"Unsupported return type for main: {return_type}")

        # Set everything back to normal after it's compiled
        self.compiler.env = previous_env
        self.compiler.env.define(name, func, return_type)

        self.compiler.builder = previous_builder

    def visit_assign_statement(self, node: AssignStatement) -> None:
        name: str = node.ident.value
        operator: str = node.operator
        value: Expression = node.right_value

        # Check if the variable exists
        if self.compiler.env.lookup(name) is None:
            self.compiler.errors.append(f'COMPILE ERROR: Identifier {name} has not been declared before it was re-assigned')
            return

        # Resolve the right-hand value
        try:
            right_value, right_type = self.compiler.__resolve_value(value)
        except Exception as e:
            self.compiler.errors.append(f'COMPUTE ERROR: Failed to resolve value for identifier {name}: {e}')
            return

        # Get the variable pointer and original value
        var_ptr, _ = self.compiler.env.lookup(name)
        orig_value = self.compiler.builder.load(var_ptr)

        # Define supported operators
        supported_operators = {'=', '+=', '-=', '*=', '/='}

        # Check if the operator is valid
        if operator not in supported_operators:
            self.compiler.errors.append(f'COMPILE ERROR: Unsupported assignment operator "{operator}" for identifier {name}')
            return

        # Extract type information
        orig_type = orig_value.type
        right_is_int = isinstance(right_type, ir.IntType)
        right_is_float = isinstance(right_type, ir.FloatType)
        orig_is_int = isinstance(orig_type, ir.IntType)
        orig_is_float = isinstance(orig_type, ir.FloatType)

        # Helper function: Type conversion
        def convert_to_int(value):
            return self.compiler.builder.fptosi(value, ir.IntType(32)) if isinstance(value.type, ir.FloatType) else value

        def convert_to_float(value):
            return self.compiler.builder.sitofp(value, ir.FloatType()) if isinstance(value.type, ir.IntType) else value

        # Helper function: Perform operation
        def perform_operation(op, left, right):
            if op == '=':
                return right
            elif op == '+=':
                return self.compiler.builder.fadd(convert_to_float(left), convert_to_float(right))
            elif op == '-=':
                return self.compiler.builder.fsub(convert_to_float(left), convert_to_float(right))
            elif op == '*=':
                return self.compiler.builder.fmul(convert_to_float(left), convert_to_float(right))
            elif op == '/=':
                if right == 0:
                    self.compiler.errors.append(f'COMPILE ERROR: Division by zero for identifier {name}')
                    return None
                return self.compiler.builder.fdiv(convert_to_float(left), convert_to_float(right))

        # Perform the operation
        value = perform_operation(operator, orig_value, right_value)
        if value is None:
            return  # Exit if an error occurs (e.g., division by zero)

        # Ensure the types match before storing
        if isinstance(value.type, ir.FloatType) and isinstance(orig_type, ir.IntType):
            value = convert_to_int(value)
        elif isinstance(value.type, ir.IntType) and isinstance(orig_type, ir.FloatType):
            value = convert_to_float(value)

        # Store the result
        self.compiler.builder.store(value, var_ptr)

    def visit_if_statement(self, node: IfStatement) -> None:
        condition = node.condition
        consequence = node.consequence
        alternative = node.alternative

        test, _ = self.compiler.helper_methods.resolve_value(condition)

        if alternative is None:
            with self.compiler.builder.if_then(test):
                self.compiler.compile(consequence)
        else:
            with self.compiler.builder.if_else(test) as (true, otherwise):
                with true:
                    self.compiler.compile(consequence)
                with otherwise:
                    self.compiler.compile(alternative)

    def visit_while_statement(self, node: WhileStatement) -> None:
        condition: Expression = node.condition
        body: BlockStatement = node.body

        test, _ = self.compiler.__resolve_value(condition)

        while_loop_entry = self.compiler.builder.append_basic_block(f'while_loop_entry_{self.compiler.__increment_counter()}')
        while_loop_otherwise = self.compiler.builder.append_basic_block(f'while_loop_otherwise_{self.compiler.counter}')

        self.compiler.builder.cbranch(test, while_loop_entry, while_loop_otherwise)
        self.compiler.builder.position_at_start(while_loop_entry)
        self.compiler.compile(body)
        test, _ = self.compiler.__resolve_value(condition)

        self.compiler.builder.cbranch(test, while_loop_entry, while_loop_otherwise)
        self.compiler.builder.position_at_start(while_loop_otherwise)

    def visit_for_statement(self, node: ForStatement) -> None:
        var_declaration: LetStatement = node.var_declaration
        condition: Expression = node.condition
        action: AssignStatement = node.action
        body: BlockStatement = node.body

        previous_env = self.compiler.env
        self.compiler.env = Environment(parent=previous_env)

        self.compiler.compile(var_declaration)

        for_loop_entry = self.compiler.builder.append_basic_block(f'for_loop_entry_{self.compiler.__increment_counter()}')
        for_loop_otherwise = self.compiler.builder.append_basic_block(f'for_loop_otherwise_{self.compiler.counter}')

        self.compiler.breakpoints.append(for_loop_otherwise)
        self.compiler.continues.append(for_loop_entry)

        self.compiler.builder.branch(for_loop_entry)
        self.compiler.builder.position_at_start(for_loop_entry)

        self.compiler.compile(body)
        self.compiler.compile(action)

        test, _ = self.compiler.__resolve_value(condition)

        self.compiler.builder.cbranch(test, for_loop_entry, for_loop_otherwise)

        self.compiler.builder.position_at_start(for_loop_otherwise)

        self.compiler.breakpoints.pop()
        self.compiler.continues.pop()

    def visit_break_statement(self, node: BreakStatement) -> None:
        self.compiler.builder.branch(self.compiler.breakpoints[-1])

    def visit_continue_statement(self, node: ContinueStatement) -> None:
        self.compiler.builder.branch(self.compiler.continues[-1])
