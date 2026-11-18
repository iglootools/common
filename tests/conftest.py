from typing import NoReturn

import pytest


@pytest.fixture
def monkeypatch() -> NoReturn:
    """Replace pytest's fixture for every test: tests do not patch."""
    pytest.fail(
        "The monkeypatch fixture is disabled: inject a fake through a parameter"
        " instead (guidelines/coding/general.md, Mocks).",
        pytrace=False,
    )
