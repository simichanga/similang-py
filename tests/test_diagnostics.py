"""
Unit tests for the DiagnosticEngine and related utilities.
"""
import io
import pytest
from util.diagnostics import DiagnosticEngine, Severity, SourceLocation, Diagnostic


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_engine(source: str = "", **kwargs) -> tuple[DiagnosticEngine, io.StringIO]:
    buf = io.StringIO()
    engine = DiagnosticEngine(source_text=source, stream=buf, color=False, **kwargs)
    return engine, buf


# ---------------------------------------------------------------------------
# Basic emission
# ---------------------------------------------------------------------------
class TestBasicEmit:
    def test_error_increments_count(self):
        eng, _ = _make_engine()
        eng.error("something broke")
        assert eng.error_count == 1
        assert eng.has_errors()

    def test_warning_increments_count(self):
        eng, _ = _make_engine()
        eng.warning("watch out")
        assert eng.warning_count == 1
        assert not eng.has_errors()

    def test_note_does_not_count_as_error(self):
        eng, _ = _make_engine()
        eng.note("just a note")
        assert eng.error_count == 0
        assert eng.warning_count == 0

    def test_multiple_errors(self):
        eng, _ = _make_engine()
        eng.error("err1")
        eng.error("err2")
        eng.warning("warn1")
        assert eng.error_count == 2
        assert eng.warning_count == 1

    def test_reset(self):
        eng, _ = _make_engine()
        eng.error("err")
        eng.warning("warn")
        eng.reset()
        assert eng.error_count == 0
        assert eng.warning_count == 0
        assert len(eng.diagnostics) == 0


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------
class TestFormatting:
    def test_error_output_contains_message(self):
        eng, buf = _make_engine()
        eng.error("bad things")
        output = buf.getvalue()
        assert "error" in output
        assert "bad things" in output

    def test_location_in_output(self):
        eng, buf = _make_engine(filename="test.simi")
        eng.error("oops", loc=SourceLocation(line=3, col=5))
        output = buf.getvalue()
        assert "test.simi:3:5" in output

    def test_source_context_printed(self):
        source = "let x: int = 5;\nlet y: bad = 10;\nlet z: int = 0;"
        eng, buf = _make_engine(source=source, filename="test.simi")
        eng.error("unknown type 'bad'", loc=SourceLocation(line=2, col=8))
        output = buf.getvalue()
        assert "let y: bad = 10;" in output
        assert "^" in output

    def test_hint_printed(self):
        eng, buf = _make_engine()
        eng.error("bad type", hint="did you mean 'int'?")
        output = buf.getvalue()
        assert "did you mean 'int'?" in output


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
class TestSummary:
    def test_no_diagnostics(self):
        eng, buf = _make_engine()
        result = eng.summary()
        assert "no diagnostics" in result

    def test_error_summary(self):
        eng, buf = _make_engine()
        eng.error("e1")
        eng.error("e2")
        result = eng.summary()
        assert "2 errors" in result

    def test_mixed_summary(self):
        eng, buf = _make_engine()
        eng.error("e1")
        eng.warning("w1")
        eng.warning("w2")
        result = eng.summary()
        assert "1 error" in result
        assert "2 warnings" in result


# ---------------------------------------------------------------------------
# Diagnostic record
# ---------------------------------------------------------------------------
class TestDiagnosticRecord:
    def test_format_without_loc(self):
        d = Diagnostic(severity=Severity.ERROR, message="test")
        s = d.format(color=False)
        assert "error: test" in s

    def test_format_with_loc(self):
        d = Diagnostic(
            severity=Severity.WARNING,
            message="unused",
            loc=SourceLocation(line=1, col=5, filename="a.simi"),
        )
        s = d.format(color=False)
        assert "a.simi:1:5" in s
        assert "warning: unused" in s


# ---------------------------------------------------------------------------
# Source location
# ---------------------------------------------------------------------------
class TestSourceLocation:
    def test_str_full(self):
        loc = SourceLocation(line=10, col=3, filename="foo.simi")
        assert str(loc) == "foo.simi:10:3"

    def test_str_no_file(self):
        loc = SourceLocation(line=5, col=1)
        assert str(loc) == "5:1"

    def test_str_unknown(self):
        loc = SourceLocation()
        assert str(loc) == "<unknown>"


# ---------------------------------------------------------------------------
# Fatal severity exits
# ---------------------------------------------------------------------------
class TestFatalExits:
    def test_fatal_raises_system_exit(self):
        eng, _ = _make_engine()
        with pytest.raises(SystemExit):
            eng.emit(Severity.FATAL, "cannot continue")


# ---------------------------------------------------------------------------
# Max-errors limit
# ---------------------------------------------------------------------------
class TestMaxErrors:
    def test_suppresses_after_max(self):
        eng, buf = _make_engine()
        eng.max_errors = 3
        for i in range(10):
            eng.error(f"error {i}")
        output = buf.getvalue()
        assert "too many errors" in output
        # Errors beyond max should still be counted
        assert eng.error_count == 10
