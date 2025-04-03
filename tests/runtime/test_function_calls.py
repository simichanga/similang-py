import unittest
from utils.executor import execute_code
from pipeline.compiler import Compiler
from pipeline.parser import Parser
from pipeline.lexer import Lexer

class TestFunctionCalls(unittest.TestCase):
    def compile_and_execute(self, code):
        lexer = Lexer(source=code)
        parser = Parser(lexer=lexer)
        program = parser.parse_program()
        
        if len(parser.errors) > 0:
            self.fail(f"Parser errors: {parser.errors}")
        
        compiler = Compiler()
        compiler.compile(node=program)
        
        return execute_code(compiler.module)

    def test_simple_function_call(self):
        code = """
        fn add(a: int, b: int) -> int {
            return a + b;
        }
        
        fn main() -> int {
            return add(5, 10);
        }
        """
        result = self.compile_and_execute(code)
        self.assertEqual(result, 15)

    def test_function_with_type_conversion(self):
        code = """
        fn multiply(a: int, b: float) -> float {
            return a * b;
        }
        
        fn main() -> float {
            return multiply(5, 3.0);
        }
        """
        result = self.compile_and_execute(code)
        self.assertEqual(result, 15.0)
