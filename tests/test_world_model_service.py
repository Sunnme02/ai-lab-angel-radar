import pytest

from src.services.world_model_service import normalize_direction


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("core", "core"),
        ("world model", "core"),
        ("robotics", "embodied"),
        ("具身", "embodied"),
        ("4d", "driving"),
        ("自动驾驶", "driving"),
    ],
)
def test_normalize_direction_aliases(value, expected):
    assert normalize_direction(value) == expected


def test_normalize_direction_rejects_unknown():
    with pytest.raises(ValueError):
        normalize_direction("quantum espresso")

