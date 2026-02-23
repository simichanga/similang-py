from __future__ import annotations
import logging
import time
from ctypes import CFUNCTYPE, c_int, c_void_p
import llvmlite.binding as llvm

from util.config import Config

logger = logging.getLogger("similang.executor")


def _apply_llvm_passes(mod: llvm.ModuleRef, target: llvm.TargetMachine,
                        opt_level: int, size_level: int) -> None:
    """
    Apply LLVM new-pass-manager optimizations at the given level.

    ``opt_level`` maps to LLVM speed levels 0–3.
    ``size_level`` maps to LLVM size levels 0–2.
    """
    if opt_level <= 0 and size_level <= 0:
        return  # -O0: emit code as-is

    pto = llvm.PipelineTuningOptions(speed_level=opt_level, size_level=size_level)

    # Tunables based on level
    pto.loop_unrolling = opt_level >= 2
    pto.loop_interleaving = opt_level >= 2
    pto.loop_vectorization = opt_level >= 2
    pto.slp_vectorization = opt_level >= 3

    pb = llvm.create_pass_builder(target, pto)

    # Run module-level optimization pipeline
    mpm = pb.getModulePassManager()
    mpm.run(mod, pb)

    logger.debug("LLVM passes applied (speed=%d, size=%d)", opt_level, size_level)


def execute_module(module, opt_level: int | None = None,
                   size_level: int | None = None) -> int:
    """
    Execute the LLVM module using MCJIT and return the integer return code from `main`.

    Parameters
    ----------
    module : llvmlite.ir.Module
        The generated IR module (or anything with a useful ``str()``).
    opt_level : int, optional
        LLVM speed optimization level (0-3).  Falls back to ``Config.OPT_LEVEL``.
    size_level : int, optional
        LLVM size optimization level (0-2).  Falls back to ``Config.SIZE_LEVEL``.
    """
    if opt_level is None:
        opt_level = Config.OPT_LEVEL
    if size_level is None:
        size_level = Config.SIZE_LEVEL

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

    # ----- optimization passes -----
    if Config.LLVM_OPT:
        _apply_llvm_passes(mod, target, opt_level, size_level)

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
