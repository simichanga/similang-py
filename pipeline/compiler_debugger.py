from llvmlite import ir

def debug_compiler(module: ir.Module) -> None:
    print('===== COMPILER DEBUG =====')
    path = 'debug/ir.ll'
    with open(path, 'w') as f:
        f.write(str(module))
    print(f'Wrote IR to `{path}` successfully.')
