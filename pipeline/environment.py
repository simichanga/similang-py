from llvmlite import ir
from typing import Optional, Dict, Tuple

class VariableNotFoundError(Exception):
    """Exception raised when a variable is not found in the environment."""
    pass

class Environment:
    def __init__(
            self,
            records: Optional[Dict[str, Tuple[ir.Value, ir.Type]]] = None,
            parent: Optional['Environment'] = None,
            name: str = 'global'
    ) -> None:
        self.records: Dict[str, Tuple[ir.Value, ir.Type]] = records if records else {}
        self.parent: Optional['Environment'] = parent
        self.name: str = name

    def define(self, name: str, value: ir.Value, _type: ir.Type) -> ir.Value:
        """
        Define a variable in the environment.

        :param name: The name of the variable.
        :param value: The LLVM IR value of the variable.
        :param _type: The LLVM IR type of the variable.
        :return: The LLVM IR value of the variable.
        """
        self.records[name] = (value, _type)
        return value

    def lookup(self, name: str) -> Tuple[ir.Value, ir.Type]:
        """
        Look up a variable in the environment.

        :param name: The name of the variable.
        :return: A tuple containing the LLVM IR value and type of the variable.
        :raises VariableNotFoundError: If the variable is not found.
        """
        result = self.__resolve(name)
        # TODO: fix this check
        # if result is None:
        #     raise VariableNotFoundError(f"Variable '{name}' not found in environment '{self.name}'.")
        return result

    def __resolve(self, name: str) -> Optional[Tuple[ir.Value, ir.Type]]:
        """
        Resolve a variable in the environment.

        :param name: The name of the variable.
        :return: A tuple containing the LLVM IR value and type of the variable, or None if not found.
        """
        if name in self.records:
            return self.records[name]
        elif self.parent:
            return self.parent.__resolve(name)
        else:
            return None