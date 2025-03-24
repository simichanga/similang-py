import time
from ctypes import CFUNCTYPE, c_int
import llvmlite.binding as llvm

from utils.config import Config

def execute_code(module) -> int:
    """
    Executes the compiled LLVM module and returns the result of the `main` function.
    """
    llvm.initialize()
    llvm.initialize_native_target()
    llvm.initialize_native_asmprinter()

    llvm_ir_parsed = llvm.parse_assembly(str(module))
    llvm_ir_parsed.verify()

    target_machine = llvm.Target.from_default_triple().create_target_machine()
    engine = llvm.create_mcjit_compiler(llvm_ir_parsed, target_machine)
    engine.finalize_object()

    entry = engine.get_function_address('main')
    cfunc = CFUNCTYPE(c_int)(entry)

    st = time.time()
    result = cfunc()
    et = time.time()

    if Config.SHOW_EXECUTION_OUTPUT:
        print(f'\nProgram returned: {result}\nExecuted in {round((et - st) * 1000, 6)} ms.')

    return result
