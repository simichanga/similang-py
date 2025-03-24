import unittest

from core_pipeline.compiler import Compiler
from core_pipeline.parser import Parser
from core_pipeline.lexer import Lexer
from core_pipeline.ast import AssignStatement
from pipeline.executor import execute_code


class TestForLoopWithPostfixIncrement(unittest.TestCase):
    def test_for_loop_with_postfix_increment(self):
        code = """
        fn main() -> int {
            let sum: int = 0;
            for (let i: int = 0; i < 10; i++) {
                sum += i;
            }
            printf("Suma este %i", sum);
        }
        """
        lexer = Lexer(source=code)
        parser = Parser(lexer=lexer)
        program = parser.parse_program()

        if len(parser.errors) > 0:
            self.fail(f"Parser errors: {parser.errors}")

        compiler = Compiler()
        compiler.compile(node=program)

        # Execute and assert the result
        result = execute_code(compiler.module)
        self.assertEqual(result['sum'], 45)


if __name__ == '__main__':
    unittest.main()
