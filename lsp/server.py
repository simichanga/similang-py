"""
Similang Language Server.

Provides:
  - Diagnostics (parse errors, semantic errors)
  - Document symbols (functions, variables)
  - Hover (type information)
  - Go-to-definition
  - Completion (keywords, types, identifiers)

Usage:
    python -m lsp.server          # stdio transport (for VS Code)
    python -m lsp.server --tcp    # TCP transport (for debugging, port 2087)
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from lsprotocol import types as lsp
from pygls.server import LanguageServer

from lsp.analysis import AnalysisResult, analyze_document

# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------
logger = logging.getLogger("similang.lsp")

server = LanguageServer("similang-language-server", "v0.1.0")

# Cache of analysis results per URI
_analysis_cache: dict[str, AnalysisResult] = {}


def _analyze_and_publish(uri: str, text: str) -> AnalysisResult:
    """Run the Similang frontend on *text* and publish diagnostics."""
    result = analyze_document(text, uri)
    _analysis_cache[uri] = result
    server.publish_diagnostics(
        uri,
        result.diagnostics,
    )
    return result


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------
@server.feature(lsp.INITIALIZED)
def _on_initialized(params: lsp.InitializedParams) -> None:
    logger.info("Similang language server initialized")


# ---------------------------------------------------------------------------
# Document sync — full text on open/change/save
# ---------------------------------------------------------------------------
@server.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
def _on_open(params: lsp.DidOpenTextDocumentParams) -> None:
    _analyze_and_publish(params.text_document.uri, params.text_document.text)


@server.feature(lsp.TEXT_DOCUMENT_DID_CHANGE)
def _on_change(params: lsp.DidChangeTextDocumentParams) -> None:
    # Full sync — the last content change is the entire document
    if params.content_changes:
        text = params.content_changes[-1].text
        _analyze_and_publish(params.text_document.uri, text)


@server.feature(lsp.TEXT_DOCUMENT_DID_SAVE)
def _on_save(params: lsp.DidSaveTextDocumentParams) -> None:
    if params.text is not None:
        _analyze_and_publish(params.text_document.uri, params.text)


@server.feature(lsp.TEXT_DOCUMENT_DID_CLOSE)
def _on_close(params: lsp.DidCloseTextDocumentParams) -> None:
    uri = params.text_document.uri
    _analysis_cache.pop(uri, None)
    # Clear diagnostics for closed documents
    server.publish_diagnostics(uri, [])


# ---------------------------------------------------------------------------
# Document symbols — outline of functions & variables
# ---------------------------------------------------------------------------
@server.feature(lsp.TEXT_DOCUMENT_DOCUMENT_SYMBOL)
def _on_document_symbol(
    params: lsp.DocumentSymbolParams,
) -> Optional[list[lsp.DocumentSymbol]]:
    result = _analysis_cache.get(params.text_document.uri)
    if result is None:
        return None
    return result.symbols


# ---------------------------------------------------------------------------
# Hover — type info on identifiers
# ---------------------------------------------------------------------------
@server.feature(lsp.TEXT_DOCUMENT_HOVER)
def _on_hover(params: lsp.HoverParams) -> Optional[lsp.Hover]:
    result = _analysis_cache.get(params.text_document.uri)
    if result is None:
        return None
    pos = params.position
    for hover in result.hovers:
        r = hover.range
        if r is None:
            continue
        if (r.start.line <= pos.line <= r.end.line and
                r.start.character <= pos.character <= r.end.character):
            return hover
    return None


# ---------------------------------------------------------------------------
# Go-to-definition
# ---------------------------------------------------------------------------
@server.feature(lsp.TEXT_DOCUMENT_DEFINITION)
def _on_definition(
    params: lsp.DefinitionParams,
) -> Optional[lsp.Location]:
    result = _analysis_cache.get(params.text_document.uri)
    if result is None:
        return None
    pos = params.position
    for name, loc in result.definitions.items():
        # Check if cursor is on a usage of this name
        for usage_range in result.usages.get(name, []):
            if (usage_range.start.line <= pos.line <= usage_range.end.line and
                    usage_range.start.character <= pos.character <= usage_range.end.character):
                return loc
    return None


# ---------------------------------------------------------------------------
# Completion — keywords, types, in-scope identifiers
# ---------------------------------------------------------------------------
@server.feature(
    lsp.TEXT_DOCUMENT_COMPLETION,
    lsp.CompletionOptions(trigger_characters=[".", ":"]),
)
def _on_completion(
    params: lsp.CompletionParams,
) -> lsp.CompletionList:
    result = _analysis_cache.get(params.text_document.uri)
    items: list[lsp.CompletionItem] = []

    # Keywords
    for kw in _KEYWORDS:
        items.append(lsp.CompletionItem(
            label=kw,
            kind=lsp.CompletionItemKind.Keyword,
            insert_text=_KEYWORD_SNIPPETS.get(kw, kw),
            insert_text_format=lsp.InsertTextFormat.Snippet
            if kw in _KEYWORD_SNIPPETS else lsp.InsertTextFormat.PlainText,
        ))

    # Built-in types
    for t in _BUILTIN_TYPES:
        items.append(lsp.CompletionItem(
            label=t,
            kind=lsp.CompletionItemKind.TypeParameter,
        ))

    # Identifiers from analysis
    if result:
        for name, info in result.scope_symbols.items():
            kind = (lsp.CompletionItemKind.Function
                    if info.get("kind") == "function"
                    else lsp.CompletionItemKind.Variable)
            detail = info.get("type", "")
            items.append(lsp.CompletionItem(
                label=name,
                kind=kind,
                detail=detail,
            ))

    return lsp.CompletionList(is_incomplete=False, items=items)


_KEYWORDS = [
    "let", "fn", "return", "if", "else", "while", "for",
    "break", "continue", "true", "false",
]

_KEYWORD_SNIPPETS = {
    "fn": "fn ${1:name}(${2:params}) -> ${3:int} {\n\t$0\n}",
    "let": "let ${1:name}: ${2:int} = ${3:0};",
    "if": "if (${1:condition}) {\n\t$0\n}",
    "while": "while ${1:condition} {\n\t$0\n}",
    "for": "for (let ${1:i}: int = ${2:0}; ${1:i} < ${3:10}; ${1:i}++) {\n\t$0\n}",
    "return": "return ${1:value};",
}

_BUILTIN_TYPES = [
    "int", "float", "bool", "str", "void",
    "i8", "i16", "i32", "i64",
    "u8", "u16", "u32", "u64",
    "f32", "f64",
    "string", "char",
]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Similang Language Server")
    parser.add_argument("--tcp", action="store_true", help="Use TCP transport")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2087)
    parser.add_argument("--log", default="warning",
                        choices=["debug", "info", "warning", "error"])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log.upper()),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    if args.tcp:
        logger.info("Starting Similang LSP on %s:%d", args.host, args.port)
        server.start_tcp(args.host, args.port)
    else:
        logger.info("Starting Similang LSP on stdio")
        server.start_io()


if __name__ == "__main__":
    main()
