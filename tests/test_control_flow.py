import os
import tempfile
import pytest
from main import main as similang_main


def run_simi_code(source: str, capsys) -> str:
    """Helper to write a temp .simi file and run the compiler."""
    with tempfile.NamedTemporaryFile("w", suffix=".simi", delete=False) as f:
        f.write(source)
        f.flush()
        filepath = f.name

    try:
        similang_main([filepath])
        captured = capsys.readouterr()
        return captured.out.strip()
    finally:
        os.remove(filepath)


def test_if_else_true_branch(capsys):
    source = """
    fn main() -> int {
        if 1 == 1 {
            printf("true branch\\n");
        } else {
            printf("false branch\\n");
        }
        return 0;
    }
    """
    out = run_simi_code(source, capsys)
    assert out == "true branch"


def test_if_else_false_branch(capsys):
    source = """
    fn main() -> int {
        if 2 < 1 {
            printf("true branch\\n");
        } else {
            printf("false branch\\n");
        }
        return 0;
    }
    """
    out = run_simi_code(source, capsys)
    assert out == "false branch"


def test_for_loop_sum(capsys):
    source = """
    fn main() -> int {
        let sum: int = 0;
        for (let i: int = 0; i < 5; i++) {
            sum += i;
        }
        printf("%d\\n", sum);
        return 0;
    }
    """
    out = run_simi_code(source, capsys)
    assert out == "10"  # 0+1+2+3+4


def test_break_in_loop(capsys):
    source = """
    fn main() -> int {
        for (let i: int = 0; i < 10; i++) {
            if i == 3 {
                break;
            }
            printf("%d ", i);
        }
        return 0;
    }
    """
    out = run_simi_code(source, capsys)
    assert out == "0 1 2"


def test_continue_in_loop(capsys):
    source = """
    fn main() -> int {
        for (let i: int = 0; i < 5; i++) {
            if i == 2 {
                continue;
            }
            printf("%d ", i);
        }
        return 0;
    }
    """
    out = run_simi_code(source, capsys)
    assert out == "0 1 3 4"
