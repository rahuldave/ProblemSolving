"""The tests' web requests write the statement log to a temporary file, not to v2/logs/."""

import pytest


@pytest.fixture(autouse=True, scope="session")
def statement_log(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("TUTOR_LOG", str(tmp_path_factory.mktemp("log") / "statements.jsonl"))
    yield
    mp.undo()
