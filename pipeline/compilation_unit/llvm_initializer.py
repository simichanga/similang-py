from typing import List, Tuple, Optional, Callable, Dict
import logging
from llvmlite import ir

logging.basicConfig(level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")

class LLVMInitializer:
    PRINT_FUNCTION_NAME = 'printf'
    TRUE_CONSTANT_NAME = 'true'
    FALSE_CONSTANT_NAME = 'false'

    @staticmethod
    def init_printf(module: ir.Module, type_map: Dict[str, ir.Type]) -> ir.Function:
        """Initialize the printf function."""
        fnty: ir.FunctionType = ir.FunctionType(
            ir.IntType(32),  # Assuming printf returns int
            [ir.IntType(8).as_pointer()],  # Format string pointer
            var_arg=True
        )
        return ir.Function(module, fnty, LLVMInitializer.PRINT_FUNCTION_NAME)

    @staticmethod
    def init_booleans(module: ir.Module, type_map: Dict[str, ir.Type]) -> tuple[ir.GlobalVariable, ir.GlobalVariable]:
        """Initialize global boolean constants."""
        bool_type: ir.Type = type_map['bool']

        true_var = ir.GlobalVariable(module, bool_type, LLVMInitializer.TRUE_CONSTANT_NAME)
        true_var.initializer = ir.Constant(bool_type, 1)
        true_var.global_constant = True

        false_var = ir.GlobalVariable(module, bool_type, LLVMInitializer.FALSE_CONSTANT_NAME)
        false_var.initializer = ir.Constant(bool_type, 0)
        false_var.global_constant = True

        return true_var, false_var