from __future__ import annotations
from typing import Dict, Optional, Tuple, Any, List

class VariableNotFoundError(Exception):
    pass

class Environment:
    """
    Simple nested-scope environment used by Codegen and lowerer.

    API:
      - define(name, value, type_name) -> stores symbol in current scope
      - lookup(name) -> (value, type_name) or raise VariableNotFoundError
      - enter() / leave() -> manage nested scopes
    """

    def __init__(self):
        # stack of dicts (each dict: name -> (value, type_name))
        self._scopes: List[Dict[str, Tuple[Any, str]]] = [{}]

    def enter(self) -> None:
        """Enter a new nested scope."""
        self._scopes.append({})

    def leave(self) -> None:
        """Leave the current scope."""
        if len(self._scopes) == 1:
            # avoid popping the global scope
            self._scopes[0].clear()
        else:
            self._scopes.pop()

    def define(self, name: str, value: Any, type_name: str) -> None:
        """
        Define symbol in the current (innermost) scope.

        :param name: symbol name
        :param value: an IR object (alloca pointer, GlobalVariable, or Function)
        :param type_name: language-level type name (e.g. 'int','float','bool','str','void' or function return type)
        """
        self._scopes[-1][name] = (value, type_name)

    def lookup(self, name: str) -> Tuple[Any, str]:
        """
        Lookup a symbol in the environment (search innermost -> outer scopes).
        Raises VariableNotFoundError if not present.
        """
        for scope in reversed(self._scopes):
            if name in scope:
                return scope[name]
        raise VariableNotFoundError(f"Variable or function '{name}' not found")
