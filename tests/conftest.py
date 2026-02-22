"""Conftest for the tests/ package.

The backend/tests/conftest.py replaces src.matching.engine with a MagicMock in
sys.modules (to prevent sentence-transformers from loading during FastAPI startup).
That works fine for backend tests, but breaks our engine unit tests in this directory
which need the *real* module.

Problem: pytest imports ALL conftest.py files before importing any test modules.
The command-line argument order determines conftest loading order: tests/ is specified
first, so tests/conftest.py runs, then backend/tests/conftest.py runs and puts the
mock back. Then test files are imported and get the mock's JobMatcher.

Fix: Use pytest_sessionstart hook, which fires AFTER all conftest files are loaded
but BEFORE test item collection begins. This ensures that when test_engine_concurrent.py
and test_save_match_results.py are imported during collection, sys.modules has the
real src.matching.engine module.
"""

import sys


def pytest_sessionstart(session):
    """Restore the real src.matching.engine before test collection.

    This hook fires after all plugins/conftest files are registered, so it runs
    after backend/tests/conftest.py has injected its mock. We evict the mock so
    that test_engine_concurrent.py and test_save_match_results.py bind to the
    real JobMatcher / GeminiStats when their top-level imports execute.
    """
    if "src.matching.engine" in sys.modules:
        del sys.modules["src.matching.engine"]
    import src.matching.engine  # noqa: F401
