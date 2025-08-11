# test_assignments.py

import unittest
import io
import sys
from pipeline.lexer import Lexer
from pipeline.parser import Parser
from pipeline.compiler import Compiler
from utils.executor import execute_code

class TestAssignments(unittest.TestCase):
    def compile_and_execute(self, code):
        lexer = Lexer(code)
        parser = Parser(lexer)
        program = parser.parse_program()

        if len(parser.errors) > 0:
            self.fail(f"Parser errors: {parser.errors}")

        compiler = Compiler()
        compiler.compile(node=program)

        # Capture stdout to capture printf output
        old_stdout = sys.stdout
        new_stdout = io.StringIO()
        sys.stdout = new_stdout

        try:
            result = execute_code(compiler.module)
        finally:
            sys.stdout = old_stdout

        output = new_stdout.getvalue().strip()

        return result, output

    def test_boolean_assignment(self):
        code = """
        fn main() -> int {
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
        self.assertEqual(result, (10, ''))

    def test_float_assignment(self):
        code = """
        fn main() -> int {
            let num: float = 3.5;
            let output: bool = num == 3.5;
            return output;
        }
        """
        result = self.compile_and_execute(code)
        self.assertEqual(result, (1, ''))

    def test_composite_assignment_add(self):
        code = """
        fn main() -> int {
            let num: int = 10;
            num += 5;
            printf("%d\\n", num);
        }
        """
        _, output = self.compile_and_execute(code)
        self.assertIn("15", output)

    def test_composite_assignment_subtract(self):
        code = """
        fn main() -> int {
            let num: int = 10;
            num -= 5;
            printf("%d\\n", num);
        }
        """
        output = self.compile_and_execute(code)
        self.assertIn("5", output)

    def test_composite_assignment_multiply(self):
        code = """
        fn main() -> int {
            let num: int = 10;
            num *= 2;
            printf("%d\\n", num);
        }
        """
        output = self.compile_and_execute(code)
        self.assertIn("20", output)

    def test_composite_assignment_divide(self):
        code = """
        fn main() -> int {
            let num: int = 10;
            num /= 2;
            printf("%d\\n", num);
        }
        """
        output = self.compile_and_execute(code)
        self.assertIn("5", output)

    def test_composite_assignment_float_add(self):
        code = """
        fn main() -> float {
            let num: float = 10.0;
            num += 5.5;
            printf("%f\\n", num);
        }
        """
        output = self.compile_and_execute(code)
        self.assertIn("15.5", output)

    def test_composite_assignment_float_subtract(self):
        code = """
        fn main() -> float {
            let num: float = 10.0;
            num -= 5.5;
            printf("%f\\n", num);
        }
        """
        output = self.compile_and_execute(code)
        self.assertIn("4.5", output)

    def test_composite_assignment_float_multiply(self):
        code = """
        fn main() -> float {
            let num: float = 10.0;
            num *= 2.5;
            printf("%f\\n", num);
        }
        """
        output = self.compile_and_execute(code)
        self.assertIn("25.0", output)

    def test_composite_assignment_float_divide(self):
        code = """
        fn main() -> float {
            let num: float = 10.0;
            num /= 2.5;
            printf("%f\\n", num);
        }
        """
        output = self.compile_and_execute(code)
        self.assertIn("4.0", output)

    def test_mixed_type_assignment(self):
        code = """
        fn main() -> float {
            let num: int = 10;
            let float_num: float = 5.5;
            num += float_num;
            printf("%f\\n", num);
        }
        """
        output = self.compile_and_execute(code)
        self.assertIn("15.5", output)

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
