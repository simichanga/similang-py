import unittest
from pipeline.executor import execute_code
from core_pipeline.compiler import Compiler
from core_pipeline.parser import Parser
from core_pipeline.lexer import Lexer

class TestEdgeCases(unittest.TestCase):
    def compile_and_execute(self, code):
        lexer = Lexer(source=code)
        parser = Parser(lexer=lexer)
        program = parser.parse_program()
        
        if len(parser.errors) > 0:
            self.fail(f"Parser errors: {parser.errors}")
        
        compiler = Compiler()
        compiler.compile(node=program)
        
        return execute_code(compiler.module)

    def test_type_mismatch(self):
        # Test that an error is raised when there is a type mismatch
        code = """
        fn main() -> int {
            return true + 1.0;  // Invalid operation
        }
        """
        with self.assertRaises(TypeError):
            self.compile_and_execute(code)

    def test_empty_expression(self):
        code = ""
        with self.assertRaises(SyntaxError):
            self.compile_and_execute(code)

    def test_invalid_operator(self):
        code = """
        fn main() -> int {
            return 5 ^ 3;  // Invalid operator
        }
        """
        with self.assertRaises(ValueError):
            self.compile_and_execute(code)
