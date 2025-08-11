import unittest

from pipeline.compiler import Compiler
from pipeline.parser import Parser
from pipeline.lexer import Lexer
from utils.executor import execute_code


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
        ast = parser.parse_program()

        if len(parser.errors) > 0:
            self.fail(f"Parser errors: {parser.errors}")

        compiler = Compiler()
        compiler.compile(node=ast)

        # Execute and assert the result
        result = execute_code(compiler.module)
        self.assertEqual(result['sum'], 45)


if __name__ == '__main__':
    unittest.main()
