from __future__ import annotations
import time
from ctypes import CFUNCTYPE, c_int, c_void_p
import llvmlite.binding as llvm

from util.config import Config

def execute_module(module) -> int:
    """
    Execute the LLVM module using MCJIT and return the integer return code from `main`.
    Expects `module` to be an llvmlite.ir.Module (or convertible to str()) and contain `main`.
    """
    llvm.initialize()
    llvm.initialize_native_target()
    llvm.initialize_native_asmprinter()

    llvm_ir = str(module)
    mod = llvm.parse_assembly(llvm_ir)
    try:
        mod.verify()
    except Exception as e:
        print("LLVM verify failed:", e)
        raise

    target = llvm.Target.from_default_triple().create_target_machine()
    engine = llvm.create_mcjit_compiler(mod, target)
    engine.finalize_object()
    entry = engine.get_function_address('main')
    if entry == 0:
        raise RuntimeError("The compiled module does not contain a 'main' entry point.")

    cfunc = CFUNCTYPE(c_int)(entry)
    start = time.time()
    result = cfunc()
    end = time.time()
    if Config.SHOW_EXECUTION_OUTPUT:
        print(f"Program returned: {result}")
        print(f"Execution time: {(end - start)*1000:.3f} ms")
    return result
