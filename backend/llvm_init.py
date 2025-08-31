from __future__ import annotations
from typing import Dict, Tuple
from llvmlite import ir


class LLVMInitializer:
    PRINTF_NAME = "printf"
    TRUE_NAME = "true"
    FALSE_NAME = "false"

    @staticmethod
    def declare_printf(module: ir.Module) -> ir.Function:
        """
        Declare printf: int printf(i8* fmt, ...)
        Returns an llvmlite.ir.Function object in `module`.
        """
        i32 = ir.IntType(32)
        i8ptr = ir.IntType(8).as_pointer()
        fnty = ir.FunctionType(i32, [i8ptr], var_arg=True)
        func = ir.Function(module, fnty, name=LLVMInitializer.PRINTF_NAME)
        return func

    @staticmethod
    def init_booleans(module: ir.Module) -> Tuple[ir.GlobalVariable, ir.GlobalVariable]:
        """
        Create internal boolean globals named 'true' and 'false' of type i1.
        """
        i1 = ir.IntType(1)
        true_gv = ir.GlobalVariable(module, i1, LLVMInitializer.TRUE_NAME)
        true_gv.linkage = 'internal'
        true_gv.global_constant = True
        true_gv.initializer = ir.Constant(i1, 1)

        false_gv = ir.GlobalVariable(module, i1, LLVMInitializer.FALSE_NAME)
        false_gv.linkage = 'internal'
        false_gv.global_constant = True
        false_gv.initializer = ir.Constant(i1, 0)

        return true_gv, false_gv
