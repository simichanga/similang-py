import json
from Parser import Parser

def debug_parser(parser: Parser, program) -> None:
    print('===== PARSER DEBUG =====')
    path = 'debug/ast.json'
    with open(path, 'w') as f:
        json.dump(program.json(), f, indent = 4)
    print(f'Wrote AST to `{path}` successfully.')
