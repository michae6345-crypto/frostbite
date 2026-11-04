import pytest

import frostbite_host.hook

REAL_CONTROLLING_TTY = frostbite_host.hook.controlling_tty


@pytest.fixture(autouse=True)
def no_real_tty(monkeypatch):
    """Tests must not depend on the terminal that runs them: two fake sessions would
    otherwise share its real tty."""
    monkeypatch.setattr(frostbite_host.hook, "controlling_tty", lambda: "")
