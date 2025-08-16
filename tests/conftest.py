import types
from pathlib import Path
import pytest

from util.debug import dump_ast, dump_ir, dump_tokens
from util.config import Config

# Optional: enable debug flags globally in tests by environment,
# or leave it controlled per-test via fixture.
Config.DEBUG = True

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Standard helper hook that stores the test's report objects on the test item.
    This lets fixtures see whether the test passed/failed in their teardown.
    """
    # execute all other hooks to obtain the report object
    outcome = yield
    rep = outcome.get_result()
    setattr(item, "rep_" + rep.when, rep)
