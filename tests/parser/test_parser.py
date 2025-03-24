import unittest
from core_pipeline.parser import Parser
from core_pipeline.lexer import Lexer
from core_pipeline.ast import AssignStatement


class TestParser(unittest.TestCase):
    def setUp(self):
        self.lexer = Lexer("")
        self.parser = Parser(self.lexer)

    def test_parse_assignment_statement_ValidAssignment_ReturnsAssignStatement(self):
        self.lexer.input = "a = 10;"
        self.lexer.tokenize()
        self.parser = Parser(self.lexer)
        statement = self.parser.__parse_assignment_statement()
        self.assertIsInstance(statement, AssignStatement)
        self.assertEqual(statement.ident.value, "a")
        self.assertEqual(statement.operator, "=")
        self.assertEqual(statement.right_value.value, 10)

    def test_parse_assignment_statement_InvalidIdentifier_ThrowsSyntaxError(self):
        self.lexer.input = "10 = 10;"
        self.lexer.tokenize()
        self.parser = Parser(self.lexer)
        with self.assertRaises(SyntaxError):
            self.parser.__parse_assignment_statement()

    def test_parse_assignment_statement_InvalidOperator_ThrowsSyntaxError(self):
        self.lexer.input = "a * 10;"
        self.lexer.tokenize()
        self.parser = Parser(self.lexer)
        with self.assertRaises(SyntaxError):
            self.parser.__parse_assignment_statement()

    def test_parse_assignment_statement_MissingSemicolon_ThrowsSyntaxError(self):
        self.lexer.input = "a = 10"
        self.lexer.tokenize()
        self.parser = Parser(self.lexer)
        with self.assertRaises(SyntaxError):
            self.parser.__parse_assignment_statement()

    def test_parse_assignment_statement_InvalidRightExpression_ThrowsSyntaxError(self):
        self.lexer.input = "a = ;"
        self.lexer.tokenize()
        self.parser = Parser(self.lexer)
        with self.assertRaises(SyntaxError):
            self.parser.__parse_assignment_statement()

if __name__ == '__main__':
    unittest.main()
