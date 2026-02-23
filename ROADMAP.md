# Similang Compiler — Roadmap

> Living document tracking what works, what needs fixing, and what to build next.  
> Last updated: 2026-02-23

---

## Current Status

### Working

| Feature | Notes |
|---------|-------|
| **Lexer** | Handles all operators, keywords, comments (`//`, `/* */`), strings, numbers, identifiers. |
| **Parser** | Pratt (top-down operator precedence). Produces a clean AST. |
| **Type system** | Canonical types `int`, `float`, `bool`, `str`, `void` + aliases (`i32`, `i64`, `u32`, `f32`, `f64`, `string`, `char`, etc.). |
| **Semantic analysis** | Name resolution, scope tracking, basic type checking, assignment compatibility, function arity. |
| **Code generation** | LLVM IR via `llvmlite`. Functions, variables, arithmetic, comparisons, control flow, `printf`. |
| **Execution** | MCJIT-based execution of the compiled `main` function. |
| **Diagnostics engine** | Coloured, source-aware error/warning/note output with caret highlighting. |
| **Debug dumps** | AST JSON, IR `.ll`, token dumps to `debug/` directory. |
| **AST optimizer** | Constant folding, dead code elimination, constant propagation with fixed-point iteration (O0–O3). |
| **LLVM optimization** | New pass manager integration with configurable speed/size levels, loop opts, vectorization. |
| **Test suite** | 232 tests (lexer, parser, sema, codegen integration, diagnostics, optimizer). |

### Known Limitations / Bugs

| Issue | Priority |
|-------|----------|
| Parser treats unknown identifiers as types in function-parameter position (no `TYPE` validation after `:` in params). | Medium |
| No source-location tracking on AST nodes (line/col not stored on nodes). | High |
| `break` / `continue` not validated by sema (only codegen catches misuse). | Medium |
| No dead-code detection or unreachable-code warnings. | Low |
| `runtime/builtins.py` has stale imports (`from similang.middle.types …`). | Low |
| No `.gitignore` for `__pycache__` / `debug/` artifacts. | Low |

---

## Roadmap

### Phase 1 — Foundations (current sprint)

- [x] Type aliases (`i32` → `int`, `f32` → `float`, etc.)
- [x] Diagnostics engine (coloured, source-aware errors/warnings/notes)
- [x] Refactor error handling across parser, sema, codegen
- [x] Thorough test suite (183 tests)
- [ ] Add source locations (line, col) to every AST node
- [ ] Propagate source locations through sema and codegen errors
- [ ] Fix parser to validate type tokens for function parameters
- [x] Add `.gitignore`

### Phase 2 — Language Essentials

- [ ] **Mutable vs immutable variables** — `let` (immutable) vs `let mut` or `var`
- [ ] **Proper scoping in codegen** — Wire `Environment.enter()` / `leave()` to block statements
- [ ] **Explicit type casts** — `x as float`, `y as int`
- [ ] **Wider integer types** — Actually distinguish `i8`/`i16`/`i32`/`i64` at the IR level (currently all map to `i32`)
- [ ] **Double-precision float** — `f64` should map to `ir.DoubleType()`, not `ir.FloatType()`
- [ ] **Unsigned integer semantics** — `u8`/`u16`/`u32`/`u64` with unsigned comparisons/division
- [ ] **String operations** — Length, concatenation, indexing
- [ ] **Char type** — Proper character literal syntax (`'a'`)
- [ ] **Array types** — `[N]T` syntax, indexing, bounds checking
- [ ] **Tuple types** — `(int, float)` unnamed product types

### Phase 3 — Control Flow & Functions

- [ ] **Else-if chains** — `if … else if … else`
- [ ] **Match / switch** — Pattern matching or switch-case
- [ ] **Do-while loop**
- [ ] **Early return** from void functions (currently no issue, but test coverage)
- [ ] **Function overloading** or **default parameters**
- [ ] **Closures / anonymous functions (lambdas)**
- [ ] **Recursion depth checking** (optional — prevents stack overflow in badly written programs)

### Phase 4 — Type System

- [ ] **User-defined type aliases** — `type MyInt = i32;`
- [ ] **Struct types** — `struct Foo { x: int, y: float }`
- [ ] **Enum types** — `enum Color { Red, Green, Blue }`
- [ ] **Trait / interface system**
- [ ] **Generics / parametric polymorphism** — `fn id<T>(x: T) -> T`
- [ ] **Option / Result types** — Possibly built on enums + generics
- [ ] **Nullable types** — `?int` or `Option<int>`

### Phase 5 — Memory & Ownership

- [ ] **Heap allocation** — `new` / `alloc`
- [ ] **Pointers** — `*T`, `&T` (raw and reference)
- [ ] **Ownership model** (Rust-inspired borrow checker, or simpler GC)
- [ ] **Automatic reference counting** as an alternative to manual memory management
- [ ] **Stack vs heap** decision annotations

### Phase 6 — Modules & Imports

- [ ] **Multi-file compilation** — `import` / `module` system
- [ ] **Namespaces / packages**
- [ ] **Standard library** — Math, I/O, string utilities, collections
- [ ] **FFI (Foreign Function Interface)** — Call C functions, link with `.o` / `.lib`
- [ ] **Header generation** for C interop

### Phase 7 — Optimisation

- [x] **Constant folding** (compile-time evaluation of `2 + 3` → `5`)
- [x] **Dead code elimination**
- [x] **Constant propagation** (single-assignment variable substitution)
- [x] **LLVM optimisation passes** — Hook into `-O0`, `-O1`, `-O2`, `-O3`
- [ ] **Inlining hints** — `inline fn`
- [ ] **Loop invariant code motion**
- [ ] **Tail call optimisation**
- [ ] **Benchmark framework** — Track compilation speed and generated code quality

### Phase 8 — Tooling & DX

- [ ] **Language Server Protocol (LSP)** — Autocomplete, go-to-definition, hover types
- [ ] **Formatter** — `similang fmt`
- [ ] **Linter** — `similang lint`
- [ ] **REPL** — Interactive mode
- [ ] **Package manager** — `similang pkg`
- [x] **Source maps** — Map generated IR/assembly back to source for debugging
- [ ] **DWARF debug info** — Emit debug metadata in the generated binary
- [ ] **Editor plugins** — VS Code extension (syntax highlighting, snippets)

### Phase 9 — Targets & Distribution

- [ ] **Native binary output** — Compile to `.exe` / ELF via LLVM's target machine
- [ ] **Cross-compilation** — ARM, RISC-V, WASM targets
- [ ] **WebAssembly backend** — Compile to `.wasm`
- [ ] **Static linking** — Produce fully self-contained binaries
- [ ] **Shared library output** — `.dll` / `.so` / `.dylib`

---

## Architecture Notes

```
Source (.simi)
    │
    ▼
┌──────────┐
│  Lexer   │  frontend/lexer.py — character stream → tokens
└────┬─────┘
     │ tokens
     ▼
┌──────────┐
│  Parser  │  frontend/parser.py — tokens → AST (Pratt parser)
└────┬─────┘
     │ AST
     ▼
┌──────────┐
│  Sema    │  middle/sema.py — name resolution, type checking
└────┬─────┘
     │ validated AST
     ▼
┌──────────┐
│Optimizer │  middle/optimizer.py — constant folding, DCE, propagation (O0–O3)
└────┬─────┘
     │ optimized AST
     ▼
┌──────────┐
│ Codegen  │  backend/codegen.py + expr_lowerer.py — AST → LLVM IR
└────┬─────┘                      ↘ source map anchors → util/source_map.py
     │ LLVM IR module
     ▼
┌──────────┐
│ LLVM Opt │  util/executor.py — new pass manager (speed/size levels)
└────┬─────┘
     │ optimized IR
     ▼
┌──────────┐
│ Executor │  util/executor.py — MCJIT compilation + execution
└──────────┘
```

Supporting modules:
- `middle/types.py` — Type system (type info, aliases, coercion rules)
- `middle/optimizer.py` — AST optimization passes (constant folding, DCE, constant propagation)
- `util/diagnostics.py` — Structured diagnostic output (errors, warnings, notes)
- `util/errors.py` — Error collector (bridges old API to diagnostics engine)
- `util/config.py` — Global configuration flags (debug, optimization levels)
- `util/debug.py` — AST/IR/token dump utilities
- `util/env.py` — Nested-scope symbol environment (used by codegen)
- `util/source_map.py` — Source maps: bidirectional IR ↔ source line mapping + JSON serialization
- `backend/llvm_init.py` — LLVM module setup (printf, booleans)
- `runtime/builtins.py` — Future runtime helper registrations
