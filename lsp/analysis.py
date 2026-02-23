"""
Document analysis for the Similang LSP.

Runs the Similang frontend pipeline (lex → parse → sema) on a document and
produces LSP-ready diagnostics, symbols, hover info, and definition locations.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from lsprotocol import types as lsp

import frontend.ast as A
from frontend.ast import SourceLocation
from frontend.lexer import Lexer
from frontend.parser import Parser
from middle.sema import SemanticAnalyzer

logger = logging.getLogger("similang.lsp.analysis")


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------
@dataclass
class AnalysisResult:
    """All LSP-ready data extracted from a single document analysis."""
    # LSP diagnostics (errors, warnings)
    diagnostics: list[lsp.Diagnostic] = field(default_factory=list)
    # Document symbols (outline)
    symbols: list[lsp.DocumentSymbol] = field(default_factory=list)
    # Hover ranges → Hover objects (keyed by source position)
    hovers: list[lsp.Hover] = field(default_factory=list)
    # Definition locations:  name → Location
    definitions: dict[str, lsp.Location] = field(default_factory=dict)
    # Usage ranges:  name → list of Range
    usages: dict[str, list[lsp.Range]] = field(default_factory=dict)
    # Scope symbols for completion:  name → {kind, type}
    scope_symbols: dict[str, dict] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _loc_to_range(loc: SourceLocation) -> lsp.Range:
    """Convert a SourceLocation to an LSP Range (0-based lines/cols)."""
    if not loc or loc.line <= 0:
        return lsp.Range(
            start=lsp.Position(line=0, character=0),
            end=lsp.Position(line=0, character=0),
        )
    start_line = loc.line - 1
    start_col = max(0, loc.col - 1)
    end_line = (loc.end_line - 1) if loc.end_line else start_line
    end_col = loc.end_col if loc.end_col else start_col + 1
    return lsp.Range(
        start=lsp.Position(line=start_line, character=start_col),
        end=lsp.Position(line=end_line, character=end_col),
    )


def _make_diagnostic(
    message: str,
    loc: Optional[SourceLocation] = None,
    severity: lsp.DiagnosticSeverity = lsp.DiagnosticSeverity.Error,
) -> lsp.Diagnostic:
    """Create an LSP Diagnostic from a message and optional source location."""
    rng = _loc_to_range(loc) if loc else lsp.Range(
        start=lsp.Position(line=0, character=0),
        end=lsp.Position(line=0, character=0),
    )
    return lsp.Diagnostic(
        range=rng,
        message=message,
        severity=severity,
        source="similang",
    )


# ---------------------------------------------------------------------------
# Symbol extraction (AST walk)
# ---------------------------------------------------------------------------
def _extract_symbols(
    program: A.Program,
    uri: str,
    result: AnalysisResult,
) -> None:
    """Walk the AST and populate symbols, hovers, definitions, usages."""
    for stmt in program.statements:
        if isinstance(stmt, A.FunctionStatement):
            _extract_function(stmt, uri, result)
        elif isinstance(stmt, A.LetStatement):
            _extract_let(stmt, uri, result, parent_name=None)


def _extract_function(
    fn: A.FunctionStatement,
    uri: str,
    result: AnalysisResult,
) -> None:
    """Extract symbol info from a function declaration."""
    name = fn.name.value if fn.name else "<anonymous>"
    loc = fn.loc
    fn_range = _loc_to_range(loc)

    # Build parameter signature
    params_str = ", ".join(
        f"{p.name}: {p.value_type}" for p in (fn.parameters or [])
    )
    ret = fn.return_type or "void"
    detail = f"fn({params_str}) -> {ret}"

    # Children: parameters + body variables
    children: list[lsp.DocumentSymbol] = []

    # Parameters as children
    for param in (fn.parameters or []):
        param_loc = getattr(param, 'loc', None) or loc
        param_range = _loc_to_range(param_loc) if param_loc else fn_range
        children.append(lsp.DocumentSymbol(
            name=param.name,
            kind=lsp.SymbolKind.Variable,
            range=param_range,
            selection_range=param_range,
            detail=param.value_type,
        ))
        # Add to scope for completion
        result.scope_symbols[param.name] = {
            "kind": "variable",
            "type": param.value_type,
        }

    # Walk function body for let statements
    if fn.body:
        for stmt in fn.body.statements:
            if isinstance(stmt, A.LetStatement):
                child_sym = _extract_let(stmt, uri, result, parent_name=name)
                if child_sym:
                    children.append(child_sym)
            # Walk nested blocks for variables
            _walk_for_identifiers(stmt, uri, result)

    symbol = lsp.DocumentSymbol(
        name=name,
        kind=lsp.SymbolKind.Function,
        range=fn_range,
        selection_range=fn_range,
        detail=detail,
        children=children if children else None,
    )
    result.symbols.append(symbol)

    # Definition location
    result.definitions[name] = lsp.Location(uri=uri, range=fn_range)

    # Scope symbol
    result.scope_symbols[name] = {
        "kind": "function",
        "type": detail,
    }

    # Hover: on the function name
    if fn.name and fn.name.loc:
        name_range = _loc_to_range(fn.name.loc)
        result.hovers.append(lsp.Hover(
            contents=lsp.MarkupContent(
                kind=lsp.MarkupKind.Markdown,
                value=f"```similang\n{detail}\n```",
            ),
            range=name_range,
        ))


def _extract_let(
    stmt: A.LetStatement,
    uri: str,
    result: AnalysisResult,
    parent_name: Optional[str],
) -> Optional[lsp.DocumentSymbol]:
    """Extract symbol info from a let statement."""
    if stmt.name is None:
        return None
    name = stmt.name.value
    loc = stmt.loc
    var_range = _loc_to_range(loc)
    detail = stmt.value_type or "unknown"

    symbol = lsp.DocumentSymbol(
        name=name,
        kind=lsp.SymbolKind.Variable,
        range=var_range,
        selection_range=var_range,
        detail=detail,
    )

    # Only add as top-level symbol if not inside a function
    if parent_name is None:
        result.symbols.append(symbol)

    # Definition location
    result.definitions[name] = lsp.Location(uri=uri, range=var_range)

    # Scope symbol
    result.scope_symbols[name] = {
        "kind": "variable",
        "type": detail,
    }

    # Hover: on the variable name
    if stmt.name.loc:
        name_range = _loc_to_range(stmt.name.loc)
        result.hovers.append(lsp.Hover(
            contents=lsp.MarkupContent(
                kind=lsp.MarkupKind.Markdown,
                value=f"```similang\nlet {name}: {detail}\n```",
            ),
            range=name_range,
        ))

    return symbol


def _walk_for_identifiers(
    node: A.Node,
    uri: str,
    result: AnalysisResult,
) -> None:
    """Walk an AST node tree to collect identifier usages for go-to-def."""
    if isinstance(node, A.IdentifierLiteral):
        name = node.value
        if node.loc:
            rng = _loc_to_range(node.loc)
            result.usages.setdefault(name, []).append(rng)
    elif isinstance(node, A.CallExpression):
        if isinstance(node.function, A.IdentifierLiteral):
            name = node.function.value
            if node.function.loc:
                rng = _loc_to_range(node.function.loc)
                result.usages.setdefault(name, []).append(rng)
        for arg in (node.arguments or []):
            _walk_for_identifiers(arg, uri, result)
    elif isinstance(node, A.InfixExpression):
        _walk_for_identifiers(node.left_node, uri, result)
        _walk_for_identifiers(node.right_node, uri, result)
    elif isinstance(node, A.PrefixExpression):
        _walk_for_identifiers(node.right_node, uri, result)
    elif isinstance(node, A.PostfixExpression):
        _walk_for_identifiers(node.left_node, uri, result)
    elif isinstance(node, A.ReturnStatement):
        if node.return_value:
            _walk_for_identifiers(node.return_value, uri, result)
    elif isinstance(node, A.ExpressionStatement):
        if node.expr:
            _walk_for_identifiers(node.expr, uri, result)
    elif isinstance(node, A.AssignStatement):
        if node.ident:
            _walk_for_identifiers(node.ident, uri, result)
        if node.right_value:
            _walk_for_identifiers(node.right_value, uri, result)
    elif isinstance(node, A.LetStatement):
        if node.value:
            _walk_for_identifiers(node.value, uri, result)
    elif isinstance(node, A.IfStatement):
        if node.condition:
            _walk_for_identifiers(node.condition, uri, result)
        if node.consequence:
            for s in node.consequence.statements:
                _walk_for_identifiers(s, uri, result)
        if node.alternative:
            for s in node.alternative.statements:
                _walk_for_identifiers(s, uri, result)
    elif isinstance(node, A.WhileStatement):
        if node.condition:
            _walk_for_identifiers(node.condition, uri, result)
        if node.body:
            for s in node.body.statements:
                _walk_for_identifiers(s, uri, result)
    elif isinstance(node, A.ForStatement):
        if node.var_declaration:
            _walk_for_identifiers(node.var_declaration, uri, result)
        if node.condition:
            _walk_for_identifiers(node.condition, uri, result)
        if node.action:
            _walk_for_identifiers(node.action, uri, result)
        if node.body:
            for s in node.body.statements:
                _walk_for_identifiers(s, uri, result)
    elif isinstance(node, A.BlockStatement):
        for s in node.statements:
            _walk_for_identifiers(s, uri, result)


# ---------------------------------------------------------------------------
# Main analysis entry point
# ---------------------------------------------------------------------------
def analyze_document(text: str, uri: str = "") -> AnalysisResult:
    """
    Run the full Similang analysis pipeline on *text* and return LSP data.

    Even if parsing or semantic analysis fails, partial results are returned
    so the user always gets diagnostics.
    """
    result = AnalysisResult()

    if not text.strip():
        return result

    # ---- Lexing + Parsing ----
    try:
        lexer = Lexer(text)
        parser = Parser(lexer)
        program = parser.parse_program()
    except Exception as exc:
        result.diagnostics.append(_make_diagnostic(f"Parse crash: {exc}"))
        return result

    # Collect parser errors
    if parser.error_collector.has_errors():
        for err in parser.error_collector.errors:
            msg = err.format() if hasattr(err, 'format') else str(err)
            # Try to extract line number from the error message
            loc = None
            if hasattr(err, 'line'):
                loc = SourceLocation(line=err.line, col=0)
            result.diagnostics.append(
                _make_diagnostic(msg, loc, lsp.DiagnosticSeverity.Error)
            )

    # ---- Semantic analysis ----
    try:
        sema = SemanticAnalyzer()
        ok, errors = sema.analyze(program)
        if not ok:
            for err_msg in errors:
                result.diagnostics.append(
                    _make_diagnostic(err_msg, severity=lsp.DiagnosticSeverity.Error)
                )
    except Exception as exc:
        result.diagnostics.append(
            _make_diagnostic(f"Sema crash: {exc}", severity=lsp.DiagnosticSeverity.Error)
        )

    # ---- Extract symbols / hovers / defs from AST ----
    try:
        _extract_symbols(program, uri, result)
    except Exception as exc:
        logger.warning("Symbol extraction failed: %s", exc)

    return result
