import unittest
from Lexer import Lexer
from Parser import Parser
from Compiler import Compiler
from pipeline.executor import execute_code

class TestAssignments(unittest.TestCase):
    def compile_and_execute(self, code):
        lexer = Lexer(source=code)
        parser = Parser(lexer=lexer)
        program = parser.parse_program()

        if len(parser.errors) > 0:
            self.fail(f"Parser errors: {parser.errors}")

        compiler = Compiler()
        compiler.compile(node=program)

        return execute_code(compiler.module)

    def test_boolean_assignment(self):
        code = """
        fn main() -> bool {
            let cond: bool = 22 == 22;
            return cond;
        }
        """
        result = self.compile_and_execute(code)
        self.assertTrue(result)

    def test_int_assignment(self):
        code = """
        fn main() -> int {
            let num: int = 10;
            return num;
        }
        """
        result = self.compile_and_execute(code)
        self.assertEqual(result, 10)

    def test_float_assignment(self):
        code = """
        fn main() -> float {
            let num: float = 3.5;
            return num;
        }
        """
        result = self.compile_and_execute(code)
        self.assertAlmostEqual(result, 3.5)

    def test_composite_assignment_add(self):
        code = """
        fn main() -> int {
            let num: int = 10;
            num += 5;
            return num;
        }
        """
        result = self.compile_and_execute(code)
        self.assertEqual(result, 15)

    def test_composite_assignment_subtract(self):
        code = """
        fn main() -> int {
            let num: int = 10;
            num -= 5;
            return num;
        }
        """
        result = self.compile_and_execute(code)
        self.assertEqual(result, 5)

    def test_composite_assignment_multiply(self):
        code = """
        fn main() -> int {
            let num: int = 10;
            num *= 2;
            return num;
        }
        """
        result = self.compile_and_execute(code)
        self.assertEqual(result, 20)

    def test_composite_assignment_divide(self):
        code = """
        fn main() -> int {
            let num: int = 10;
            num /= 2;
            return num;
        }
        """
        result = self.compile_and_execute(code)
        self.assertEqual(result, 5)

    def test_composite_assignment_float_add(self):
        code = """
        fn main() -> float {
            let num: float = 10.0;
            num += 5.5;
            return num;
        }
        """
        result = self.compile_and_execute(code)
        self.assertAlmostEqual(result, 15.5)

    def test_composite_assignment_float_subtract(self):
        code = """
        fn main() -> float {
            let num: float = 10.0;
            num -= 5.5;
            return num;
        }
        """
        result = self.compile_and_execute(code)
        self.assertAlmostEqual(result, 4.5)

    def test_composite_assignment_float_multiply(self):
        code = """
        fn main() -> float {
            let num: float = 10.0;
            num *= 2.5;
            return num;
        }
        """
        result = self.compile_and_execute(code)
        self.assertAlmostEqual(result, 25.0)

    def test_composite_assignment_float_divide(self):
        code = """
        fn main() -> float {
            let num: float = 10.0;
            num /= 2.5;
            return num;
        }
        """
        result = self.compile_and_execute(code)
        self.assertAlmostEqual(result, 4.0)

    def test_mixed_type_assignment(self):
        code = """
        fn main() -> float {
            let num: int = 10;
            let float_num: float = 5.5;
            num += float_num;
            return num;
        }
        """
        result = self.compile_and_execute(code)
        self.assertAlmostEqual(result, 15.5)

    def test_invalid_assignment(self):
        code = """
        fn main() -> int {
            let num: int = 10;
            num = "hello";  // Invalid assignment
            return num;
        }
        """
        with self.assertRaises(Exception):
            self.compile_and_execute(code)

if __name__ == "__main__":
    unittest.main()
