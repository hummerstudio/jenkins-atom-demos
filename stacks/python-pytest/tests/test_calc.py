import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from calc import add, divide


def test_adds():
    assert add(2, 3) == 5


def test_divides():
    assert divide(9, 3) == 3


def test_refuses_to_divide_by_zero():
    with pytest.raises(ValueError):
        divide(1, 0)
