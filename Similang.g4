grammar Similang;

// The top-level rule for a program, which consists of a sequence of statements followed by the end of file (EOF).
program
    : statement* EOF
    ;

// A statement can be one of several types: letStatement, functionStatement, returnStatement, ifStatement,
// whileStatement, forStatement, breakStatement, continueStatement, expressionStatement, printfStatement,
// or assignStatement.
statement
    : letStatement
    | functionStatement
    | returnStatement
    | ifStatement
    | whileStatement
    | forStatement
    | breakStatement
    | continueStatement
    | expressionStatement
    | printfStatement
    | assignStatement
    ;

// A let statement declares a variable with an optional type and initializes it with an expression.
letStatement
    : 'let' IDENT (':' type)? '=' expression ';'
    ;

// An assign statement updates the value of an existing variable using an assignment operator.
assignStatement
    : IDENT assignmentOperator expression ';'
    ;

// A function statement defines a function with a name, optional parameters, an optional return type, and a block of statements.
functionStatement
    : 'fn' IDENT '(' functionParameterList? ')' (':' type)? blockStatement
    ;

// A return statement exits a function and optionally returns a value.
returnStatement
    : 'return' expression ';'
    ;

// An if statement executes a block of statements if a condition is true, with an optional else block for false.
ifStatement
    : 'if' '(' expression ')' blockStatement ('else' blockStatement)?
    ;

// A while statement repeatedly executes a block of statements as long as a condition is true.
whileStatement
    : 'while' '(' expression ')' blockStatement
    ;

// A for statement initializes a variable, checks a condition, updates the variable, and executes a block of statements.
forStatement
    : 'for' '(' letStatement expression ';' assignStatement ')' blockStatement
    ;

// A break statement exits the nearest enclosing loop.
breakStatement
    : 'break' ';'
    ;

// A continue statement skips the rest of the current iteration of the nearest enclosing loop.
continueStatement
    : 'continue' ';'
    ;

// An expression statement consists of an expression followed by a semicolon.
expressionStatement
    : expression ';'
    ;

// A printf statement prints a formatted string to the console.
printfStatement
    : 'printf' '(' argumentList ')' ';'
    ;

// An expression can be a primary expression, a binary expression (infixOperator), a prefix expression, a postfix expression, or a parenthesized expression.
expression
    : primary
    | expression infixOperator expression
    | prefixOperator expression
    | expression postfixOperator
    | '(' expression ')'
    ;

// A primary expression can be an identifier, an integer, a float, a boolean, a string, or a function call.
primary
    : IDENT
    | INT
    | FLOAT
    | BOOLEAN
    | STRING
    | functionCall
    ;

// A function parameter list consists of zero or more function parameters separated by commas.
functionParameterList
    : functionParameter (',' functionParameter)*
    ;

// A function parameter consists of an identifier and an optional type.
functionParameter
    : IDENT ':' type
    ;

// A type is an identifier representing a data type.
type
    : IDENT
    ;

// An argument list consists of zero or more expressions separated by commas.
argumentList
    : expression (',' expression)*
    ;

// A function call consists of an identifier (function name) and an optional argument list.
functionCall
    : IDENT '(' argumentList? ')'
    ;

// A block statement consists of a sequence of statements enclosed in curly braces.
blockStatement
    : '{' statement* '}'
    ;

// An infix operator is a binary operator that appears between two operands.
infixOperator
    : '+'
    | '-'
    | '*'
    | '/'
    | '%'
    | '<'
    | '<='
    | '>'
    | '>='
    | '=='
    | '!='
    ;

// A prefix operator is a unary operator that appears before its operand.
prefixOperator
    : '-'
    | '!'
    ;

// A postfix operator is a unary operator that appears after its operand.
postfixOperator
    : '++'
    | '--'
    ;

// An assignment operator is used to assign a value to a variable.
assignmentOperator
    : '='
    | '+='
    | '-='
    | '*='
    | '/='
    ;

// An identifier is a name used to identify a variable, function, or type.
IDENT
    : [a-zA-Z_][a-zA-Z0-9_]*
    ;

// An integer literal is a sequence of digits.
INT
    : [0-9]+
    ;

// A float literal is a sequence of digits followed by a decimal point and more digits.
FLOAT
    : [0-9]+ '.' [0-9]+
    ;

// A boolean literal is either 'true' or 'false'.
BOOLEAN
    : 'true'
    | 'false'
    ;

// A string literal is a sequence of characters enclosed in double quotes.
STRING
    : '"' .*? '"'
    ;

// Single-line comment starting with '//' and continuing until the end of the line.
LINE_COMMENT
    : '//' ~[\r\n]* -> skip
    ;

// Multi-line comment starting with '/*' and ending with '*/'.
BLOCK_COMMENT
    : '/*' .*? '*/' -> skip
    ;

// Whitespace characters (spaces, tabs, carriage returns, and newlines) are skipped.
WS
    : [ \t\r\n]+ -> skip
    ;
