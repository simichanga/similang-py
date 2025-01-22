import unittest
from pipeline.executor import execute_code
from Compiler import Compiler
from Parser import Parser
from Lexer import Lexer

# TODO implement implicit conversion
class TestComparisonOperators(unittest.TestCase):
    def compile_and_execute(self, code):
        lexer = Lexer(source=code)
        parser = Parser(lexer=lexer)
        program = parser.parse_program()
        
        if len(parser.errors) > 0:
            self.fail(f"Parser errors: {parser.errors}")
        
        compiler = Compiler()
        compiler.compile(node=program)
        
        return execute_code(compiler.module)

    def test_less_than(self):
        code = """
        fn main() -> bool {
            return 5 < 10;
        }
        """
        result = self.compile_and_execute(code)
        self.assertTrue(result)

    def test_greater_than(self):
        code = """
        fn main() -> bool {
            return 15 > 10;
        }
        """
        result = self.compile_and_execute(code)
        self.assertTrue(result)

    def test_less_than_or_equal(self):
        code = """
        fn main() -> bool {
            return 10 <= 10;
        }
        """
        result = self.compile_and_execute(code)
        self.assertTrue(result)

    def test_greater_than_or_equal(self):
        code = """
        fn main() -> bool {
            return 15 >= 10;
        }
        """
        result = self.compile_and_execute(code)
        self.assertTrue(result)

    def test_equal_to(self):
        code = """
        fn main() -> bool {
            return 5 == 5;
        }
        """
        result = self.compile_and_execute(code)
        self.assertTrue(result)

    def test_not_equal_to(self):
        code = """
        fn main() -> bool {
            return 5 != 10;
        }
        """
        result = self.compile_and_execute(code)
        self.assertTrue(result)

if __name__ == "__main__":
    unittest.main()
