"""Shared test fixtures. Adds the repo root to sys.path so the flat module
layout (state.py, operations.py, ...) imports without installation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import state


@pytest.fixture(autouse=True)
def silent_state_push():
    """Route state pushes to a no-op callback so tests never touch a window."""
    pushes = []
    state.set_push_callback(pushes.append)
    yield pushes
    state.set_push_callback(None)
