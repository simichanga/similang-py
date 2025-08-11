"""
Optional runtime helpers / builtin registrations for Similang.

Note: the backend.codegen already declares `printf` and boolean globals.
This module provides an optional helper to register additional builtins
or to centralize builtin definitions (string helpers, etc.).
"""
from __future__ import annotations
from llvmlite import ir
from similang.middle.types import TypeSystem
from similang.util.env import Environment

def register_runtime_builtins(module: ir.Module, env: Environment, types: TypeSystem):
    """
    Optionally register additional runtime helpers into the environment.
    Currently a no-op because Codegen declares printf and boolean globals itself,
    but this function centralizes any future runtime bindings.
    """
    # Example: declare a `puts` wrapper or other helper if you like:
    # i32 = ir.IntType(32)
    # i8ptr = ir.IntType(8).as_pointer()
    # puts_ty = ir.FunctionType(i32, [i8ptr])
    # puts = ir.Function(module, puts_ty, name="puts")
    # env.define("puts", puts, "int")
    return
