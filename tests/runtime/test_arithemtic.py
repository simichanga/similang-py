import unittest

from utils.executor import execute_code  # Assuming "execute_code" can run the compiled code and return results
from pipeline.compiler import Compiler
from pipeline.parser import Parser
from pipeline.lexer import Lexer

class TestArithmeticOperations(unittest.TestCase):
    def compile_and_execute(self, code) -> int:
        lexer = Lexer(source=code)
        parser = Parser(lexer=lexer)
        program = parser.parse_program()
        
        if len(parser.errors) > 0:
            self.fail(f"Parser errors: {parser.errors}")
        
        compiler = Compiler()
        compiler.compile(node=program)
        
        return execute_code(compiler.module)

    def test_addition(self):
        code = """
        fn main() -> int {
            return 3 + 7;
        }
        """
        result = self.compile_and_execute(code)
        self.assertEqual(result, 10)

    def test_subtraction(self):
        code = """
        fn main() -> int {
            return 15 - 8;
        }
        """
        result = self.compile_and_execute(code)
        self.assertEqual(result, 7)

    def test_multiplication(self):
        code = """
        fn main() -> int {
            return 4 * 5;
        }
        """
        result = self.compile_and_execute(code)
        self.assertEqual(result, 20)

    def test_division(self):
        code = """
        fn main() -> int {
            return 20 / 4;
        }
        """
        result = self.compile_and_execute(code)
        self.assertEqual(result, 5)

    def test_modulus(self):
        code = """
        fn main() -> int {
            return 22 % 7;
        }
        """
        result = self.compile_and_execute(code)
        self.assertEqual(result, 1)

    # def test_power(self):
    #     code = """
    #     fn main() -> int {
    #         return 2 ^ 3;
    #     }
    #     """
    #     result = self.compile_and_execute(code)
    #     self.assertEqual(result, 8)

if __name__ == "__main__":
    unittest.main()
