# Similang for VS Code

Language support for the [Similang](https://github.com/simichanga/similang-py) programming language.

## Features

### Syntax Highlighting
Full TextMate grammar for `.simi` files:
- Keywords (`fn`, `let`, `if`, `else`, `while`, `for`, `return`, `break`, `continue`)
- Types (`int`, `float`, `bool`, `str`, `void`, `i32`, `f64`, etc.)
- Functions (declarations and calls)
- Variables (declarations and references)
- Operators, strings, numbers, comments

### Language Server (LSP)
Powered by the Similang compiler frontend:
- **Diagnostics** — Parse and semantic errors shown inline
- **Hover** — Type information on functions and variables
- **Go-to-Definition** — Jump to function/variable declarations
- **Document Symbols** — Outline view of functions and variables
- **Completion** — Keywords, types, and in-scope identifiers with snippets

### Runner
- **Run Current File** (`Ctrl+Shift+R`) — Execute the current `.simi` file
- **Run Optimized** — Execute with `-O3` optimization
- **Show LLVM IR** — View the generated IR in a new tab

### Snippets
Quick templates for `fn`, `main`, `let`, `if`, `ife`, `while`, `for`, `ret`, `printf`.

## Requirements

- Python 3.12+ with `pygls` installed
- The `similang-py` project must be accessible (auto-detected from workspace or set via `similang.projectRoot`)

## Setup

1. Install the extension (or run in Extension Development Host)
2. Open a folder containing `.simi` files
3. Set `similang.projectRoot` to the path of your `similang-py` checkout if not auto-detected
4. Install the LSP dependency: `pip install pygls`

## Extension Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `similang.pythonPath` | `"python"` | Python interpreter path |
| `similang.projectRoot` | `""` | Path to similang-py root (auto-detected) |
| `similang.optimizationLevel` | `2` | Default -O level for runner |
| `similang.lsp.enable` | `true` | Enable language server |
| `similang.trace.server` | `"off"` | LSP trace level |
