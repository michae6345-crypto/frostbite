import pytest

import frostbite_host.hook

REAL_CONTROLLING_TTY = frostbite_host.hook.controlling_tty


@pytest.fixture(autouse=True)
def no_real_tty(monkeypatch):
    # Two fake sessions would otherwise share the real tty of the terminal running pytest.
    monkeypatch.setattr(frostbite_host.hook, "controlling_tty", lambda: "")
