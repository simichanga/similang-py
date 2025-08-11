import types
from pathlib import Path
import pytest

from util.debug import dump_ast, dump_ir, dump_tokens
from util.config import Config

# Optional: enable debug flags globally in tests by environment,
# or leave it controlled per-test via fixture.
Config.DEBUG = True

def pytest_runtest_makereport(item, call):
    """
    Standard helper hook that stores the test's report objects on the test item.
    This lets fixtures see whether the test passed/failed in their teardown.
    """
    # This hook needs to yield to get the report in newer pytest versions,
    # but the simple pattern below is often used. If using pytest >=7, the simpler
    # not-yield form works as pytest will call it with the `call` argument.
    # The following pattern is robust across pytest versions:
    outcome = yield from getattr(pytest, "_pytest_internal", lambda *a, **k: None)() if False else None  # no-op for static analyzers
    # The 'yield from' above is just an annotation-safe no-op; the actual hook body below:
    # (Note: if you hit a "yield outside generator" error, use the simple non-generator form:
    #     rep = item.config.hook.pytest_report_teststatus(item=item, call=call)
    # but the implementation below uses the typical pattern.)
