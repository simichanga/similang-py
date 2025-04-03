import unittest
from utils.executor import execute_code
from pipeline.compiler import Compiler
from pipeline.parser import Parser
from pipeline.lexer import Lexer

class TestImplicitConversion(unittest.TestCase):
    def compile_and_execute(self, code):
        lexer = Lexer(source=code)
        parser = Parser(lexer=lexer)
        program = parser.parse_program()
        
        if len(parser.errors) > 0:
            self.fail(f"Parser errors: {parser.errors}")
        
        compiler = Compiler()
        compiler.compile(node=program)
        
        return execute_code(compiler.module)

    def test_int_to_float_conversion(self):
        code = """
        fn main() -> float {
            return 5 + 3.0;
        }
        """
        result = self.compile_and_execute(code)
        self.assertEqual(result, 8.0)

    def test_bool_to_int_conversion(self):
        code = """
        fn main() -> int {
            return true + 1;
        }
        """
        result = self.compile_and_execute(code)
        self.assertEqual(result, 2)

    def test_bool_to_float_conversion(self):
        code = """
        fn main() -> float {
            return true + 1.0;
        }
        """
        result = self.compile_and_execute(code)
        self.assertEqual(result, 2.0)
