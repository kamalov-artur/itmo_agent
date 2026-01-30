import pytest
from src.sdlc_agents.utils import add

def test_add():
    assert add(1, 2) == 3